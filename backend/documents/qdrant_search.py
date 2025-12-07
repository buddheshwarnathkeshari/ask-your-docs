# backend/documents/qdrant_search.py
import os
import logging
import requests
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "documents")

_client = None


def client():
    global _client
    if _client is None:
        url = QDRANT_URL.rstrip("/")
        if QDRANT_API_KEY:
            _client = QdrantClient(url=url, api_key=QDRANT_API_KEY)
        else:
            _client = QdrantClient(url=url)
    return _client


def _normalize_result_item(item):
    """
    Normalize various qdrant-client return shapes into dict with id, score, payload.
    `item` may be a ScoredPoint, tuple, or plain dict depending on client version.
    """
    try:
        # object-like (ScoredPoint)
        if hasattr(item, "id") or hasattr(item, "payload"):
            pid = getattr(item, "id", None)
            score = getattr(item, "score", None)
            payload = getattr(item, "payload", None) or {}
            return {"id": str(pid) if pid is not None else None, "score": score, "payload": payload}

        # dict-like shapes
        if isinstance(item, dict):
            # shape: { "point": { "id": ..., "payload": {...}}, "score": ... }
            if "point" in item and isinstance(item["point"], dict):
                pt = item["point"]
                pid = pt.get("id")
                payload = pt.get("payload") or {}
                score = item.get("score")
                return {"id": str(pid) if pid is not None else None, "score": score, "payload": payload}

            # shape: {"id": ..., "score": ..., "payload": {...}}
            pid = item.get("id")
            score = item.get("score")
            payload = item.get("payload") or {}
            return {"id": str(pid) if pid is not None else None, "score": score, "payload": payload}

        # fallback
        return {"id": None, "score": None, "payload": {}}
    except Exception:
        logger.exception("Failed to normalize qdrant item: %r", item)
        return {"id": None, "score": None, "payload": {}}


def _build_filter(project_id):
    if not project_id:
        return None
    return {
        "must": [
            {
                "key": "project_id",
                "match": {"value": str(project_id)}
            }
        ]
    }


def search_vectors(query_embedding, top_k=6, project_id=None):
    """
    Query Qdrant for nearest vectors restricted to a project.
    Returns list of dicts: {id, score, payload}.

    Strict: raises ValueError if project_id is not provided.
    """
    if not project_id:
        raise ValueError("project_id is required for search_vectors() — refusing cross-project search.")

    qc = client()
    qfilter = _build_filter(project_id)

    # 1) Preferred modern qdrant-client signature
    try:
        resp = qc.search(
            collection_name=COLLECTION,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True,
            with_vector=False,
            filter=qfilter
        )
        return [_normalize_result_item(r) for r in resp]
    except TypeError as e:
        logger.debug("qdrant-client keyword signature mismatch (try fallback): %s", e)
    except Exception as exc:
        logger.warning("qdrant search (kw) failed, trying fallbacks: %s", exc)

    # 2) Older client signature fallback (positional / different arg names)
    try:
        resp = qc.search(COLLECTION, query_embedding, top=top_k, with_payload=True, filter=qfilter)
        return [_normalize_result_item(r) for r in resp]
    except TypeError as e:
        logger.debug("fallback positional signature mismatch: %s", e)
    except Exception as exc:
        logger.warning("fallback1 qdrant search failed: %s", exc)

    # 3) Another fallback: positional without filter kw
    try:
        resp = qc.search(COLLECTION, query_embedding, top=top_k, with_payload=True)
        return [_normalize_result_item(r) for r in resp]
    except Exception as exc:
        logger.debug("fallback2 failed: %s", exc)

    # 4) Raw HTTP fallback to Qdrant REST API (most robust)
    try:
        url = QDRANT_URL.rstrip("/") + f"/collections/{COLLECTION}/points/search"
        payload = {
            "vector": query_embedding,
            "limit": top_k,
            "with_payload": True
        }
        if qfilter:
            payload["filter"] = qfilter

        headers = {"Content-Type": "application/json"}
        if QDRANT_API_KEY:
            # Qdrant may accept API key header depending on setup; include if set
            headers["api-key"] = QDRANT_API_KEY

        logger.debug("Qdrant raw HTTP search POST %s (filter=%s)", url, bool(qfilter))
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        body = r.json()

        # extract points from possible response shapes
        pts = None
        if isinstance(body, dict):
            if "result" in body:
                if isinstance(body["result"], dict) and "points" in body["result"]:
                    pts = body["result"]["points"]
                elif isinstance(body["result"], list):
                    pts = body["result"]
                else:
                    pts = body.get("result")
            elif "points" in body:
                pts = body["points"]

        if pts is None:
            pts = []

        results = []
        for p in pts:
            if "point" in p and isinstance(p["point"], dict):
                pid = p["point"].get("id")
                payload = p["point"].get("payload") or {}
                score = p.get("score")
                results.append({"id": str(pid), "score": score, "payload": payload})
            else:
                pid = p.get("id")
                score = p.get("score")
                payload = p.get("payload") or {}
                results.append({"id": str(pid), "score": score, "payload": payload})
        return results
    except Exception as exc:
        logger.exception("Raw HTTP fallback to Qdrant failed: %s", exc)
        raise
