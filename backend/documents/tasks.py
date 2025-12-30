from celery import shared_task
from django.conf import settings
from .models import Document, DocumentChunk, DocumentStatus
from .utils import extract_text_from_pdf, chunk_text, sha256_text
import os
from core.clients.gemini import gemini_service
from core.clients.qdrant import qdrant_service
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def ingest_document_task(self, doc_id: str):
    """
    Full ingestion:
    - read Document.metadata.path (relative to MEDIA_ROOT)
    - extract text pages
    - chunk text
    - batch embed chunks, upsert to Qdrant
    """
    try:
        doc = Document.objects.get(id=doc_id)
        doc.update_status(DocumentStatus.INGESTING)

        path = doc.metadata.get("path")
        if not path:
            doc.update_status(DocumentStatus.ERROR)
            return {"error": "no path in metadata"}
    
        # resolve storage path; default_storage saved path relative to MEDIA_ROOT
        full_path = os.path.join(settings.MEDIA_ROOT, path)

        # extract
        pages = extract_text_from_pdf(full_path)  # list of (page_no, text)

        to_upsert_ids, to_upsert_payloads = [], []
        created_chunks = []

        for page_no, page_text in pages:
            chunks = chunk_text(
                page_text, 
                chunk_tokens=settings.CHUNK_TOKENS,
                overlap=settings.CHUNK_OVERLAP
            )
            for idx, chunk in enumerate(chunks):
                chunk_hash = sha256_text(chunk)

                chunk_obj = DocumentChunk.objects.create(
                    document=doc,
                    text=chunk,
                    project=doc.project,   # new
                    page=page_no,
                    chunk_index=idx,
                    token_count=len(chunk.split()),
                    chunk_hash=chunk_hash
                )
                created_chunks.append(chunk_obj)

                # prepare payload & id for qdrant
                point_id = str(chunk_obj.id)
                payload = {
                    "document_id": str(doc.id),
                    "chunk_id": point_id,   
                    "project_id": str(doc.project.id) if doc.project else None,
                    "page": page_no,
                    "chunk_index": idx,
                    "text": chunk,                    # full chunk text
                    "chunk_text": chunk,              # alias 
                    "text_snippet": chunk[:800],       # short preview for quick embeds / UI
                    "is_deleted": False
                }
                to_upsert_ids.append(point_id)
                # we'll fill vectors in batches below
                to_upsert_payloads.append(payload)

                texts = [p["text_snippet"] for p in to_upsert_payloads]
                vectors = gemini_service.embed_batch(texts)
                qdrant_service.upsert_vectors(to_upsert_ids, vectors, to_upsert_payloads)
                to_upsert_ids, to_upsert_payloads = [], []

        doc.update_status(DocumentStatus.DONE)
        return {"status": "ok", "created_chunks": len(created_chunks)}
    except Exception as exc:
        doc.update_status(DocumentStatus.ERROR)
        raise self.retry(exc=exc)
