# documents/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.core.files.storage import default_storage
from django.conf import settings
from .serializers import DocumentListSerializer
from .serializers import UploadSerializer
from .models import Document
from .tasks import ingest_document_task   # <-- UPDATED

import hashlib


class DocumentListView(APIView):
    """
    GET /api/documents/?project_id=<uuid>
    Returns list of documents. If project_id provided, filters by project.
    """
    permission_classes = [permissions.AllowAny]   # dev convenience; change later

    def get(self, request):
        qs = Document.objects.all().order_by("-uploaded_at")
        project_id = request.query_params.get("project_id")
        if project_id:
            # if your Document model has a FK to Project, use that instead.
            # If you store project id in metadata, adapt accordingly.
            # Example when Document has project FK: qs = qs.filter(project_id=project_id)
            qs = qs.filter(project_id=project_id)
            # NOTE: above tries to support JSONField metadata — adjust if you store project differently.
        serializer = DocumentListSerializer(qs, many=True)
        return Response(serializer.data)

class UploadView(APIView):
    """
    Handles document upload:
      1. Validates upload
      2. Computes SHA-256 to ensure idempotency
      3. Saves file to MEDIA_ROOT/uploads/
      4. Creates Document record
      5. Dispatches async ingestion task (Celery)
    """

    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = serializer.validated_data["file"]
        file_bytes = uploaded_file.read()

        # -------- Idempotency using SHA-256 --------
        sha = hashlib.sha256(file_bytes).hexdigest()
        # existing = Document.objects.filter(sha256=sha).first()
        # if existing:
        #     return Response(
        #         {"status": "exists", "id": str(existing.id)},
        #         status=status.HTTP_200_OK,
        #     )

        # -------- Save file to MEDIA_ROOT/uploads --------
        storage_path = f"uploads/{uploaded_file.name}"
        saved_path = default_storage.save(storage_path, uploaded_file)

        #   before creating doc, resolve project
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        project = None
        if project_id:
            from projects.models import Project
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                return Response({"detail":"project not found"}, status=status.HTTP_400_BAD_REQUEST)
            
        # -------- Create Document entry --------
        doc = Document.objects.create(
            filename=uploaded_file.name,
            sha256=sha,
            size=len(file_bytes),
            metadata={"path": saved_path},
            project_id=project_id,
            status="queued",
        )

        # -------- Trigger background ingestion task --------
        ingest_document_task.delay(str(doc.id))

        return Response(
            {"status": "queued", "id": str(doc.id)},
            status=status.HTTP_201_CREATED,
        )
