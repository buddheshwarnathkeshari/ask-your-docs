# backend/documents/tasks.py
from celery import shared_task
from django.conf import settings
from .models import Document, DocumentChunk
from .utils import extract_text_from_pdf, chunk_text, sha256_text
import os
from .qdrant_client import QdrantClientWrapper
from .gemini_client import gemini_embed_batch

BATCH_SIZE = int(os.getenv("EMBED_BATCH", 64))
EMBED_DIM = int(os.getenv("EMBED_DIM", 768))
QDRANT_COLL = os.getenv("QDRANT_COLLECTION_NAME", "documents")

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def ingest_document_task(self, doc_id: str):
    """
    Full ingestion:
    - read Document.metadata.path (relative to MEDIA_ROOT)
    - extract text pages
    - chunk text
    - create DocumentChunk rows (idempotent by chunk_hash)
    - batch embed chunks, upsert to Qdrant
    """
    try:
        doc = Document.objects.get(id=doc_id)
        doc.status = "ingesting"
        doc.save(update_fields=["status"])

        path = doc.metadata.get("path")
        if not path:
            doc.status = "error"
            doc.save(update_fields=["status"])
            return {"error": "no path in metadata"}

        # resolve storage path; default_storage saved path relative to MEDIA_ROOT
        from django.conf import settings
        full_path = os.path.join(settings.MEDIA_ROOT, path)

        # extract
        pages = extract_text_from_pdf(full_path)  # list of (page_no, text)
        qclient = QdrantClientWrapper()

        to_upsert_ids, to_upsert_vectors, to_upsert_payloads = [], [], []
        created_chunks = []

        for page_no, page_text in pages:
            chunks = chunk_text(page_text, chunk_tokens=int(os.getenv("CHUNK_TOKENS", 600)),
                                overlap=int(os.getenv("CHUNK_OVERLAP", 80)))
            for idx, chunk in enumerate(chunks):
                chunk_hash = sha256_text(chunk)
                # idempotency: check if chunk exists
                # exists = DocumentChunk.objects.filter(chunk_hash=chunk_hash).first()
                # if exists:
                #     continue
                # create DB row
                chunk_obj = DocumentChunk.objects.create(
                    document=doc,
                    text=chunk,
                    page=page_no,
                    chunk_index=idx,
                    token_count=len(chunk.split()),
                    chunk_hash=chunk_hash
                )
                created_chunks.append(chunk_obj)

                # prepare payload & id for qdrant
                point_id = str(chunk_obj.id)
                # payload: keep doc id, page, chunk_index and short snippet
                payload = {
                    "document_id": str(doc.id),
                    "page": page_no,
                    "chunk_index": idx,
                    "text_snippet": chunk[:800]
                }
                to_upsert_ids.append(point_id)
                # we'll fill vectors in batches below
                to_upsert_payloads.append(payload)

                # batch when enough
                if len(to_upsert_ids) >= BATCH_SIZE:
                    texts = [p["text_snippet"] for p in to_upsert_payloads]
                    vectors = gemini_embed_batch(texts)
                    qclient.upsert_vectors(to_upsert_ids, vectors, to_upsert_payloads)
                    to_upsert_ids, to_upsert_vectors, to_upsert_payloads = [], [], []

        # remaining
        if to_upsert_ids:
            texts = [p["text_snippet"] for p in to_upsert_payloads]
            vectors = gemini_embed_batch(texts)
            qclient.upsert_vectors(to_upsert_ids, vectors, to_upsert_payloads)

        doc.status = "done"
        doc.save(update_fields=["status"])
        return {"status": "ok", "created_chunks": len(created_chunks)}
    except Exception as exc:
        # update doc status and bubble error
        try:
            doc.status = "error"
            doc.save(update_fields=["status"])
        except Exception:
            pass
        raise self.retry(exc=exc)
