# backend/documents/qdrant_search.py
import os
import logging
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "documents")

_client = None


def client():
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL)
    return _client


def _normalize_result_item(item):
    """
    Normalize various qdrant-client return shapes into dict with id, score, payload.
    `item` may be a ScoredPoint, tuple, or plain dict depending on client version.
    """
    # ScoredPoint / PointStruct like object
    try:
        # common attrs for newer clients
        pid = getattr(item, "id", None) or item.get("id")
        score = getattr(item, "score", None) or (item.get("score") if isinstance(item, dict) else None)
        payload = getattr(item, "payload", None) or (item.get("payload") if isinstance(item, dict) else None)
        return {"id": str(pid), "score": score, "payload": payload or {}}
    except Exception:
        logger.exception("Failed to normalize qdrant item: %r", item)
        return {"id": None, "score": None, "payload": {}}


def search_vectors(query_embedding, top_k=6):
    """
    Query Qdrant for nearest vectors.
    Returns list of dicts: {id, score, payload}.
    This implementation avoids using version-specific kwargs like `with_scores`.
    """
    qc = client()
    # prefer high-level .search where supported
    try:
        resp = qc.search(
            collection_name=COLLECTION,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True,
            # do NOT pass with_scores; some versions accept it, some don't
        )
        results = []
        for r in resp:
            results.append(_normalize_result_item(r))
        return results

    except TypeError as e:
        # fallback for older/newer client shapes: try older signature or raw api
        logger.warning("qdrant_client.search signature mismatch, falling back: %s", e)
        try:
            # older clients might expect vector param named differently
            resp = qc.search(COLLECTION, query_embedding, top=top_k, with_payload=True)
            results = []
            for r in resp:
                results.append(_normalize_result_item(r))
            return results
        except Exception as exc:
            logger.exception("Fallback qdrant search failed: %s", exc)
            raise

    except Exception as exc:
        logger.exception("Qdrant search failed: %s", exc)
        raise

