# backend/documents/qdrant_search.py
import os
import logging
import json
import requests
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "documents")

_client = None


def client():
    global _client
    if _client is None:
        # QdrantClient expects url without trailing slash
        _client = QdrantClient(url=QDRANT_URL.rstrip('/'))
    return _client


def _normalize_result_item(item):
    """
    Normalize various qdrant-client return shapes into dict with id, score, payload.
    `item` may be a ScoredPoint, tuple, or plain dict depending on client version.
    """
    try:
        # attempt common attribute access first
        if hasattr(item, "id") or hasattr(item, "payload"):
            pid = getattr(item, "id", None)
            score = getattr(item, "score", None)
            payload = getattr(item, "payload", None)
            return {"id": str(pid), "score": score, "payload": payload or {}}
        # if it's a dict-like
        if isinstance(item, dict):
            pid = item.get("id") or (item.get("point") or {}).get("id")
            score = item.get("score") or (item.get("result") or {}).get("score")
            payload = item.get("payload") or (item.get("point") or {}).get("payload") or {}
            return {"id": str(pid) if pid is not None else None, "score": score, "payload": payload or {}}
        # fallback
        return {"id": None, "score": None, "payload": {}}
    except Exception:
        logger.exception("Failed to normalize qdrant item: %r", item)
        return {"id": None, "score": None, "payload": {}}


def _build_filter(project_id):
    """Return a Qdrant filter dict when project_id is provided."""
    if not project_id:
        return None
    # ensure project_id is string
    project_val = str(project_id)
    return {
        "must": [
            {
                "key": "project_id",
                "match": {"value": project_val}
            }
        ]
    }


def search_vectors(query_embedding, top_k=6, project_id=None):
    """
    Query Qdrant for nearest vectors, optionally filtering by project_id.
    Returns list of dicts: {id, score, payload}.
    Attempts multiple client signatures and a raw HTTP fallback.
    """
    qc = client()
    qfilter = _build_filter(project_id)

    # 1) Preferred client call (newer qdrant-client)
    try:
        resp = qc.search(
            collection_name=COLLECTION,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True,
            query_filter=qfilter
        )
        results = []
        for r in resp:
            results.append(_normalize_result_item(r))
        return results
    except TypeError as e:
        logger.debug("search signature mismatch (try fallback 1): %s", e)
    except Exception as exc:
        logger.warning("preferred qdrant search failed, trying fallback(s): %s", exc)

    # 2) Older client signature fallback (positional / different arg names)
    try:
        # older signature: qc.search(collection_name, vector, top=..., with_payload=True, filter=...)
        resp = qc.search(COLLECTION, query_embedding, top=top_k, with_payload=True, filter=qfilter)
        results = [_normalize_result_item(r) for r in resp]
        return results
    except TypeError as e:
        logger.debug("fallback 2 signature mismatch: %s", e)
    except Exception as exc:
        logger.warning("fallback 2 qdrant search failed: %s", exc)

    # 3) Another common fallback: positional without kw filter
    try:
        resp = qc.search(COLLECTION, query_embedding, top=top_k, with_payload=True)
        results = [_normalize_result_item(r) for r in resp]
        return results
    except Exception as exc:
        logger.debug("fallback 3 failed: %s", exc)

    # 4) Raw HTTP fallback to Qdrant REST API (most robust)
    try:
        url = QDRANT_URL.rstrip('/') + f"/collections/{COLLECTION}/points/search"
        payload = {
            "vector": query_embedding,
            "limit": top_k,
            "with_payload": True
        }
        if qfilter:
            payload["filter"] = qfilter

        headers = {"Content-Type": "application/json"}
        logger.debug("Qdrant raw HTTP search POST %s (filter=%s)", url, bool(qfilter))
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        body = r.json()
        # body shape: {"result": {"points": [...]}} or {"result": [...]}
        pts = None
        if isinstance(body, dict) and "result" in body:
            # try both shapes
            if isinstance(body["result"], dict) and "points" in body["result"]:
                pts = body["result"]["points"]
            elif isinstance(body["result"], list):
                pts = body["result"]
            else:
                # try 'result' -> 'hits' etc.
                pts = body.get("result")
        if pts is None:
            pts = []
        results = []
        for p in pts:
            # p might be {id, payload, score, vector} or {point: {id,payload}, score:..}
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
