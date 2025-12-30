import os
import logging
import requests
import inspect
from django.conf import settings
from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

logger = logging.getLogger(__name__)

class QdrantService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize connection parameters and client."""
        self.url = settings.QDRANT_URL
        self.collection = settings.QDRANT_COLLECTION_NAME
        self.embed_dim = settings.EMBED_DIMENSION
        self.scroll_batch = 500
        self.payload_batch = 256

        # Initialize the Python Client
        self.client = QdrantClient(url=self.url)

        self._ensure_collection()

    def _ensure_collection(self):
        """Standardizes collection creation on startup."""
        try:
            documents_collection_exists = self.collection_exists(self.collection)
            if not documents_collection_exists:
                logger.info(f"Creating collection: {self.collection}")
                self.create_collection(self.collection, self.embed_dim)
        except Exception as e:
            logger.error(f"Qdrant collection check failed: {e}")
        
    def collection_exists(self, name: str) -> bool:
        collections = self.client.get_collections().collections
        return any(c.name == name for c in collections)

    def create_collection(self, name: str, dim: int):
        params = rest.VectorParams(size=dim, distance=rest.Distance.COSINE)
        self.client.recreate_collection(collection_name=name, vectors_config=params)

    def _build_filter(self, project_id):
        """Builds a filter to exclude deleted documents and scope by project."""
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
    
    def search_vectors(self, query_embedding: List[float], top_k: int = 10, project_id: str = None) -> List[Dict]:
        """Performs a filtered search, falling back to REST if the client fails."""
        if not project_id:
            raise ValueError("project_id is required for scoped search.")

        qfilter = self._build_filter(project_id)
        return self._search_via_rest(query_embedding, top_k, qfilter)

    def _search_via_rest(self, query_embedding: List[float], top_k: int, qfilter: Dict) -> List[Dict]:
        """REST fallback for search (v1beta/v1 compatible)."""
        url = f"{self.url}/collections/{self.collection}/points/search"
        payload = {
            "vector": query_embedding,
            "limit": top_k,
            "filter": qfilter,
            "with_payload": True,
            "score_threshold": 0.6
        }
        headers = {"Content-Type": "application/json"}

        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("result", [])
        return [self._normalize_item(item) for item in data]

    def upsert_vectors(self, ids: List[str], vectors: List[List[float]], payloads: List[Dict]):
        """Standardized batch upsert."""
        points = [
            rest.PointStruct(id=id_, vector=vec, payload=payload)
            for id_, vec, payload in zip(ids, vectors, payloads)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def set_document_deleted_status(self, document_id: str, is_deleted: bool = True, project_id: str = None):
        """Marks document points as deleted using batch updates."""
        point_ids = self._rest_scroll_point_ids(document_id, project_id)
        if not point_ids: return

        payload = {"is_deleted": bool(is_deleted)}
        
        # Batch update points
        for i in range(0, len(point_ids), self.payload_batch):
            batch = point_ids[i:i + self.payload_batch]
            try:
                self.client.set_payload(
                    collection_name=self.collection,
                    payload=payload,
                    points=batch
                )
            except Exception:
                # Minimal REST fallback for payload updates
                self._set_payload_rest(batch, payload)

    def _rest_scroll_point_ids(self, document_id, project_id=None):
        """
        REST fallback that pages through /collections/<coll>/points/scroll
        and returns a list of point ids (strings).
        """
        filt = {
            "must": [
                {
                    "key": "document_id", 
                    "match": {
                        "value": str(document_id)
                    }
                },
                {
                    "key": "project_id", 
                    "match": {
                        "value": str(project_id)
                    }
                }
            ]
        }
        url = self.url.rstrip("/") + f"/collections/{self.collection}/points/scroll"
        headers = {"Content-Type": "application/json"}
       
        offset = 0
        all_ids = []
        limit = self.scroll_batch

        while True:
            body = {"filter": filt, "limit": limit, "offset": offset, "with_payload": False}
            r = requests.post(url, json=body, headers=headers, timeout=30)
            r.raise_for_status()
            body_json = r.json()


            result = body_json["result"]
            pts = result["points"]

            # extract ids
            ids = []
            for p in pts:
                pid = p.get("id")
                if pid is not None:
                    ids.append(str(pid))

            all_ids.extend(ids)

            if len(ids) < limit:
                break
            offset += len(ids)

        return all_ids


    def _normalize_item(self, item: Any) -> Dict:
        """Ensures consistent dictionary output regardless of source (REST vs Client)."""
        pid = item.get("id")
        score = item.get("score")
        payload = item.get("payload") or {}

        return {"id": str(pid) if pid is not None else None, "score": score, "payload": payload}

    def _set_payload_rest(self, ids: List[str], payload: Dict):
        url = f"{self.url}/collections/{self.collection}/points/payload"
        body = {"payload": payload, "points": ids}
        headers = {"api-key": self.api_key} if self.api_key else {}
        requests.put(url, json=body, headers=headers, timeout=10)

# Single instance for the whole app
qdrant_service = QdrantService()
