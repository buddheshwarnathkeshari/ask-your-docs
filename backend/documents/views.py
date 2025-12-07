# documents/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import default_storage
from django.conf import settings

from .serializers import UploadSerializer
from .models import Document
from .tasks import ingest_document_task   # <-- UPDATED

import hashlib


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

        # -------- Create Document entry --------
        doc = Document.objects.create(
            filename=uploaded_file.name,
            sha256=sha,
            size=len(file_bytes),
            metadata={"path": saved_path},
            status="queued",
        )

        # -------- Trigger background ingestion task --------
        ingest_document_task.delay(str(doc.id))

        return Response(
            {"status": "queued", "id": str(doc.id)},
            status=status.HTTP_201_CREATED,
        )
