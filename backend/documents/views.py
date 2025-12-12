from rest_framework import viewsets, status, permissions
from documents.qdrant_search import set_document_deleted
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.db import transaction
import hashlib
import mimetypes

from .models import Document
from .serializers import DocumentListSerializer, UploadSerializer
from projects.models import Project
from .tasks import ingest_document_task


class DocumentViewSet(viewsets.ViewSet):
    """
    Supports:
    GET     /documents/                → list
    POST    /documents/                → upload
    DELETE  /documents/<id>/           → soft delete
    GET     /documents/<id>/download/  → download
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        project_id = request.query_params.get("project_id")
        qs = Document.objects.filter(is_deleted=False).order_by("-uploaded_at")
        if project_id:
            qs = qs.filter(project_id=project_id)
        serializer = DocumentListSerializer(qs, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]

        # Validate project
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        project = get_object_or_404(Project, id=project_id)

        # Compute sha256
        file_bytes = uploaded_file.read()
        sha = hashlib.sha256(file_bytes).hexdigest()

        # Duplicate detection
        existing = Document.objects.filter(sha256=sha, project_id=project_id).first()
        if existing:
            # auto-restore if deleted
            if existing.is_deleted:
                existing.is_deleted = False
                existing.save(update_fields=["is_deleted"])
                set_document_deleted(str(existing.id), deleted=False, project_id=str(existing.project.id) if existing.project else None)

            return Response(
                {
                    "status": "duplicate",
                    "id": str(existing.id),
                    "message": "This file already exists in this project."
                },
                status=status.HTTP_200_OK,
            )

        # Save file into storage
        storage_path = f"uploads/{uploaded_file.name}"
        saved_path = default_storage.save(storage_path, uploaded_file)

        # Create document
        doc = Document.objects.create(
            filename=uploaded_file.name,
            sha256=sha,
            size=len(file_bytes),
            metadata={"path": saved_path},
            project=project,
            status="queued",
        )

        ingest_document_task.delay(str(doc.id))

        return Response({"status": "queued", "id": str(doc.id)}, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        doc = get_object_or_404(Document, id=pk)
        if not doc.is_deleted:
            doc.is_deleted = True
            doc.save(update_fields=["is_deleted"])
            # mark vectors in Qdrant as deleted
            set_document_deleted(str(doc.id), deleted=True, project_id=str(doc.project.id) if doc.project else None)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        doc = get_object_or_404(Document, id=pk)
        if doc.is_deleted:
            raise Http404

        storage_path = (doc.metadata or {}).get("path")
        if not storage_path:
            return Response({"detail": "No file available"}, status=404)

        try:
            file_obj = default_storage.open(storage_path, "rb")
        except Exception:
            raise Http404

        content_type, _ = mimetypes.guess_type(doc.filename)
        return FileResponse(
            file_obj,
            as_attachment=True,
            filename=doc.filename or f"{doc.id}",
            content_type=content_type,
        )
