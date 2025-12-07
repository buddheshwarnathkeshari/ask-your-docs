import os
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http import exceptions as qexc

def _env(name, default=None):
    return os.getenv(name, default)

class QdrantClientWrapper:
    def __init__(self, url: str | None = None, collection: str | None = None, api_key: str | None = None):
        self.url = url or _env("QDRANT_URL", "http://localhost:6333")
        self.api_key = api_key or _env("QDRANT_API_KEY", None)
        self.collection = collection or _env("QDRANT_COLLECTION_NAME", "documents")
        # embedding dim must be set in env
        embed_dim = int(_env("EMBED_DIM", 768))
        self.embed_dim = embed_dim

        # instantiate client (if API key needed, pass it)
        if self.api_key:
            self.client = QdrantClient(url=self.url, api_key=self.api_key)
        else:
            self.client = QdrantClient(url=self.url)

        # ensure collection exists with correct vector params
        try:
            if not self._collection_exists(self.collection):
                self._create_collection(self.collection, self.embed_dim)
        except Exception as exc:
            # raise a helpful message in dev
            raise RuntimeError(f"Failed to ensure Qdrant collection: {exc}") from exc

    def _collection_exists(self, name: str) -> bool:
        cols = self.client.get_collections().collections
        return any(c.name == name for c in cols)

    def _create_collection(self, name: str, dim: int):
        params = rest.VectorParams(size=dim, distance=rest.Distance.COSINE)
        self.client.recreate_collection(collection_name=name, vectors_config=params)

    def upsert_vectors(self, ids: list[str], vectors: list[list[float]], payloads: list[dict]):
        """
        Upsert points to Qdrant.
        ids: list of string/ints (unique per point)
        vectors: list of list[float], len(vectors) == len(ids)
        payloads: list of dict payloads (same length)
        """
        points = [
            rest.PointStruct(id=id_, vector=vec, payload=payload)
            for id_, vec, payload in zip(ids, vectors, payloads)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(self, vector: list[float], top: int = 12):
        """
        Returns a list of qdrant search results (PointResult objects).
        """
        return self.client.search(collection_name=self.collection, query_vector=vector, limit=top)

    def health(self) -> dict:
        return {"url": self.url, "collection": self.collection, "embed_dim": self.embed_dim}
