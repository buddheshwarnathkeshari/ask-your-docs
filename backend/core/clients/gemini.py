import os
import requests
import logging
from django.conf import settings
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class GeminiService:
    _instance = None

    def __new__(cls):
        """Implement Singleton pattern to ensure only one service instance exists."""
        if cls._instance is None:
            cls._instance = super(GeminiService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Load configurations once during initialization."""
        self.api_key = settings.GEMINI_API_KEY
        self.url_root = settings.GEMINI_API_URL
        self.embed_model = settings.GEMINI_EMBED_MODEL
        self.llm_model = settings.GEMINI_LLM_MODEL

        if not (self.api_key and self.url_root and self.embed_model and self.llm_model):
            logger.error("Missing required gemini environment variables.")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Call Gemini embedContent endpoint for each text and return embeddings."""

        embeddings = []
        url = f"{self.url_root}/v1beta/models/{self.embed_model}:embedContent?key={self.api_key}"

        for text in texts:
            body = {
                "model": self.embed_model,
                "content": {"parts": [{"text": text}]}
            }
            
            resp = requests.post(url, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            embeddings.append(self._parse_embedding_response(data))
        
        return embeddings

    def _parse_embedding_response(self, data: Dict[str, Any]) -> List[float]:
        """Internal helper to extract embedding values from different API response shapes."""
        emb_obj = data.get("embedding") or {}
        values = emb_obj.get("values") or emb_obj.get("value")
        
        if values:
            return list(values)
            
        # Fallback for alternative shapes
        if "result" in data and "embedding" in data["result"]:
            res = data["result"]["embedding"]
            return list(res.get("values") or res.get("value"))
            
        raise RuntimeError(f"Unexpected embedding response shape: {data}")

    def generate_answer(self, prompt: str, temperature: float = 0.0, max_tokens: int = 500) -> Tuple[str, Dict]:
        """Calls the LLM to generate a response based on the provided prompt."""

        url = f"{self.url_root}/v1beta/models/{self.llm_model}:generateContent?key={self.api_key}"
        
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        resp = requests.post(url, json=body, timeout=60)
        if resp.status_code != 200:
            logger.error("Gemini error %s: %s", resp.status_code, resp.text)
            raise Exception(f"Gemini error {resp.status_code}: {resp.text}")

        data = resp.json()
        text = self._extract_text(data)
        
        return text, {"model": self.llm_model, "raw": data}

    def _extract_text(self, data: Dict[str, Any]) -> str:
        """Robust parser for Gemini response structures."""
        try:
            # Modern Gemini 1.5/2.x path
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return self._deep_scan_text(data)

    def _deep_scan_text(self, obj: Any) -> str:
        """Recursive fallback to find 'text' keys if the structure changes."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "text" and isinstance(v, str):
                    return v
                res = self._deep_scan_text(v)
                if res: return res
        elif isinstance(obj, list):
            for item in obj:
                res = self._deep_scan_text(item)
                if res: return res
        return ""

# Create a shared instance
gemini_service = GeminiService()