# backend/documents/qdrant_search.py
import os
import json
import logging
import requests
from qdrant_client import QdrantClient


SCROLL_BATCH = 500  # tune if needed
PAYLOAD_BATCH = 256

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "documents")

_client = None




import inspect
import json
import requests
import logging

logger = logging.getLogger(__name__)

SCROLL_BATCH = 500  # tune if needed


def _rest_scroll_point_ids(document_id, project_id=None):
    """
    REST fallback that pages through /collections/<coll>/points/scroll
    and returns a list of point ids (strings).
    """
    url = QDRANT_URL.rstrip("/") + f"/collections/{COLLECTION}/points/scroll"
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY

    filt = {"must": [{"key": "document_id", "match": {"value": str(document_id)}}]}
    if project_id:
        filt["must"].append({"key": "project_id", "match": {"value": str(project_id)}})

    offset = 0
    all_ids = []
    limit = SCROLL_BATCH

    while True:
        body = {"filter": filt, "limit": limit, "offset": offset, "with_payload": False}
        try:
            r = requests.post(url, json=body, headers=headers, timeout=30)
            r.raise_for_status()
            body_json = r.json()
        except Exception as exc:
            logger.exception("REST scroll failed for document %s: %s", document_id, exc)
            break

        pts = []
        if isinstance(body_json, dict):
            # server responses vary by version
            if "result" in body_json:
                result = body_json["result"]
                if isinstance(result, dict) and "points" in result:
                    pts = result["points"]
                elif isinstance(result, list):
                    pts = result
                else:
                    pts = result if isinstance(result, list) else []
            elif "points" in body_json:
                pts = body_json["points"]

        # extract ids
        ids = []
        for p in pts:
            # shapes: {"point": {"id": ...}} or {"id": ...}
            if isinstance(p, dict) and "point" in p and isinstance(p["point"], dict):
                pid = p["point"].get("id")
            elif isinstance(p, dict) and "id" in p:
                pid = p.get("id")
            else:
                pid = None
            if pid is not None:
                ids.append(str(pid))

        all_ids.extend(ids)

        if len(ids) < limit:
            break
        offset += len(ids)

    return all_ids


def _try_client_scroll(qc, filt):
    """
    Safely call `qc.scroll` by inspecting signature and trying a small set
    of calling styles that are known to exist across versions.
    Returns list-like `pts` as returned by the client, or None if all attempts fail.
    """
    sig = None
    try:
        sig = inspect.signature(qc.scroll)
        param_names = list(sig.parameters.keys())
    except Exception:
        param_names = []

    # Prepare candidate kwargs based on observed parameter names.
    candidates = []

    # Most modern: collection_name + query_filter
    if "collection_name" in param_names and "query_filter" in param_names:
        candidates.append({"collection_name": COLLECTION, "query_filter": filt, "with_payload": False})

    # Modern variant: collection_name + filter
    if "collection_name" in param_names and "filter" in param_names:
        candidates.append({"collection_name": COLLECTION, "filter": filt, "with_payload": False})

    # Older variant: positional collection_name + filter kw
    if "filter" in param_names:
        candidates.append({"filter": filt, "with_payload": False})

    # If param names unknown or to try a positional attempt:
    candidates.append(None)  # signals positional fallback attempts below

    # Try candidate kw calls
    for kw in candidates:
        try:
            if kw is None:
                # try a few positional forms, guarded
                try:
                    return qc.scroll(COLLECTION, filt, False)
                except Exception:
                    pass
                try:
                    # some clients use (collection, None, with_payload=False, filter=filt)
                    return qc.scroll(COLLECTION, None, False, filter=filt)
                except Exception:
                    pass
                try:
                    return qc.scroll(COLLECTION, filter=filt, with_payload=False)
                except Exception:
                    pass
                # give up this candidate and continue to REST fallback
                continue

            # safe kw call
            try:
                pts = qc.scroll(**kw)
                return pts
            except AssertionError as e:
                # client will assert on unknown kwargs; try next
                logger.debug("qc.scroll rejected kwargs %s: %s", list(kw.keys()), e)
                continue
            except TypeError as e:
                logger.debug("qc.scroll type error for kwargs %s: %s", list(kw.keys()), e)
                continue
            except Exception as exc:
                # unexpected, log and try next candidate
                logger.exception("qc.scroll attempt with kwargs %s failed: %s", list(kw.keys()), exc)
                continue
        except Exception as outer:
            # defensive - continue trying other forms
            logger.debug("qc.scroll outer exception: %s", outer)
            continue

    # all python-client attempts failed
    return None


def _get_point_ids_for_document(qc, document_id, project_id=None):
    """
    Return list of point id strings for the document (or empty list).
    Tries python-client based scroll with several guarded forms, otherwise falls back to REST.
    """
    # Build filter object expected by qdrant
    filt = {"must": [{"key": "document_id", "match": {"value": str(document_id)}}]}
    if project_id:
        filt["must"].append({"key": "project_id", "match": {"value": str(project_id)}})

    # Try the python client
    try:
        pts = _try_client_scroll(qc, filt)
        if pts is not None:
            ids = []
            for p in pts:
                # ScoredPoint/object-like:
                if hasattr(p, "id"):
                    ids.append(str(getattr(p, "id")))
                elif isinstance(p, dict):
                    # { "point": {...} } or { "id": ... }
                    if "point" in p and isinstance(p["point"], dict):
                        pid = p["point"].get("id")
                        if pid is not None:
                            ids.append(str(pid))
                    elif "id" in p:
                        ids.append(str(p.get("id")))
            return ids
    except Exception:
        logger.exception("python-client scroll attempts failed, falling back to REST scroll")

    # REST fallback (pagination)
    logger.debug("Falling back to REST scroll for document %s", document_id)
    return _rest_scroll_point_ids(document_id, project_id)

def client():
    global _client
    if _client is None:
        url = QDRANT_URL.rstrip("/")
        if QDRANT_API_KEY:
            _client = QdrantClient(url=url, api_key=QDRANT_API_KEY)
        else:
            _client = QdrantClient(url=url)
    return _client


def _build_filter(project_id):
    if not project_id:
        return None
    return {
        "must": [
            {
                "key": "project_id",
                "match": {"value": str(project_id)}
            }
        ],
        "must_not": [
            {
                "key": "is_deleted",
                "match": {"value": True}
            }
        ]
    }

def _search_via_rest(query_embedding, top_k, qfilter):
    """
    REST fallback to Qdrant /collections/<col>/points/search
    """
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
        headers["api-key"] = QDRANT_API_KEY

    r = requests.post(url, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    body = r.json()

    pts = []
    if isinstance(body, dict):
        if "result" in body:
            if isinstance(body["result"], dict) and "points" in body["result"]:
                pts = body["result"]["points"]
            elif isinstance(body["result"], list):
                pts = body["result"]
            else:
                pts = body.get("result") or []
        elif "points" in body:
            pts = body["points"]
    elif isinstance(body, list):
        pts = body

    return [_normalize_result_item(p) for p in pts]

def _normalize_result_item(item):
    # keep your existing normalization logic (same as before)
    try:
        if hasattr(item, "id") or hasattr(item, "payload"):
            pid = getattr(item, "id", None)
            score = getattr(item, "score", None)
            payload = getattr(item, "payload", None) or {}
            return {"id": str(pid) if pid is not None else None, "score": score, "payload": payload}

        if isinstance(item, dict):
            if "point" in item and isinstance(item["point"], dict):
                pt = item["point"]
                pid = pt.get("id")
                payload = pt.get("payload") or {}
                score = item.get("score")
                return {"id": str(pid) if pid is not None else None, "score": score, "payload": payload}

            pid = item.get("id")
            score = item.get("score")
            payload = item.get("payload") or {}
            return {"id": str(pid) if pid is not None else None, "score": score, "payload": payload}

        return {"id": None, "score": None, "payload": {}}
    except Exception:
        logger.exception("Failed to normalize qdrant item: %r", item)
        return {"id": None, "score": None, "payload": {}}

def set_document_deleted(document_id: str, deleted: bool = True, project_id: str | None = None):
    """
    Safely mark points for document_id as deleted/restored by MERGING payload key is_deleted.
    Uses batch set_payload via client when possible, otherwise REST per-point update.
    """
    qc = client()

    # get point ids
    point_ids = _get_point_ids_for_document(qc, document_id, project_id)
    if not point_ids:
        logger.debug("No qdrant points found for document %s (project %s)", document_id, project_id)
        return True

    payload = {"is_deleted": bool(deleted)}

    # try client.set_payload points-batched update
    for i in range(0, len(point_ids), PAYLOAD_BATCH):
        batch = point_ids[i:i + PAYLOAD_BATCH]
        updated = False
        try:
            # try kw signature
            try:
                qc.set_payload(collection_name=COLLECTION, payload=payload, points=batch)
                updated = True
            except TypeError:
                # fallback positional
                qc.set_payload(COLLECTION, payload, points=batch)
                updated = True
        except Exception as exc:
            logger.debug("qclient.set_payload failed for batch; will try REST fallback: %s", exc)

        if not updated:
            # REST fallback: use /collections/<coll>/points/payload with points list (merge semantics)
            try:
                url = QDRANT_URL.rstrip("/") + f"/collections/{COLLECTION}/points/payload"
                body = {"payload": payload, "points": [{"id": pid} for pid in batch]}
                headers = {"Content-Type": "application/json"}
                if QDRANT_API_KEY:
                    headers["api-key"] = QDRANT_API_KEY
                r = requests.put(url, json=body, headers=headers, timeout=30)
                r.raise_for_status()
                updated = True
            except Exception:
                logger.exception("REST fallback to set payload failed for batch (document %s)", document_id)
                # continue to next batch

    return True

def search_vectors(query_embedding, top_k=6, project_id=None):
    """
    Robust search that enforces exclusion of is_deleted points.
    Returns list of dicts {id, score, payload}.
    Raises ValueError if project_id is missing (keep current strictness) or if embedding empty.
    """
    if not project_id:
        raise ValueError("project_id is required for search_vectors() — refusing cross-project search.")

    qc = client()
    qfilter = _build_filter(project_id)

    # Attempt modern client signature: query_filter
    try:
        resp = qc.search(
            collection_name=COLLECTION,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True,
            with_vector=False,
            query_filter=qfilter
        )
        results = [_normalize_result_item(r) for r in resp]
    except TypeError as e_qf:
        logger.debug("qc.search(query_filter=...) failed: %s", e_qf)
        # try older client signature: filter
        try:
            resp = qc.search(
                collection_name=COLLECTION,
                query_vector=query_embedding,
                limit=top_k,
                with_payload=True,
                with_vector=False,
                filter=qfilter
            )
            results = [_normalize_result_item(r) for r in resp]
        except TypeError as e_f:
            logger.debug("qc.search(filter=...) failed: %s", e_f)
            # try positional fallback
            try:
                resp = qc.search(COLLECTION, query_embedding, top=top_k, with_payload=True, filter=qfilter)
                results = [_normalize_result_item(r) for r in resp]
            except Exception as exc_pos:
                logger.warning("qdrant python client search fallbacks failed, using REST fallback: %s", exc_pos)
                try:
                    results = _search_via_rest(query_embedding, top_k, qfilter)
                except Exception as exc_rest:
                    logger.exception("Qdrant REST search also failed: %s", exc_rest)
                    raise
    except AssertionError as ae:
        # some client versions assert unknown kwargs; fallback to REST
        logger.debug("qdrant client asserted unknown kwargs: %s", ae)
        results = _search_via_rest(query_embedding, top_k, qfilter)
    except Exception as exc:
        # unknown error from client: log and try REST
        logger.exception("Unexpected error calling qdrant-client.search: %s", exc)
        results = _search_via_rest(query_embedding, top_k, qfilter)

    # Defensive filtering: if any payloads still have is_deleted True, remove them
    filtered = []
    removed_count = 0
    for r in results:
        payload = r.get("payload") or {}
        # payload might contain "is_deleted": "true" (string) or True (bool) — normalize
        is_deleted = payload.get("is_deleted")
        if isinstance(is_deleted, str):
            # handle "true"/"false"
            is_deleted_val = is_deleted.lower() in ("1", "true", "yes", "t")
        else:
            is_deleted_val = bool(is_deleted)
        if is_deleted_val:
            removed_count += 1
            continue
        filtered.append(r)

    if removed_count:
        logger.info("search_vectors: filtered out %d deleted qdrant points for project %s", removed_count, project_id)

    return filtered