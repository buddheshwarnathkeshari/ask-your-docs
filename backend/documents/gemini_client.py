# backend/documents/gemini_client.py
import os
import requests
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
API_URL_ROOT = os.getenv("GEMINI_API_URL", "https://generativelanguage.googleapis.com")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004")
LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-1.5-flash")

# --- existing embedding implementation should remain above ---
def gemini_embed_batch(texts):
    """
    Call Google Generative Language API embedContent endpoint for each text.
    Returns list[list[float]].
    """
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing")

    embeddings = []
    for text in texts:
        url = f"{API_URL_ROOT.rstrip('/')}/v1beta/models/{EMBED_MODEL}:embedContent?key={API_KEY}"

        body = {
            "model": EMBED_MODEL,
            "content": {"parts": [{"text": text}]}
        }

        resp = requests.post(url, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Google returns embedding as either {"embedding":{"value": [...]}} or {"embedding":{"values":[...]}}
        emb = None
        emb_obj = data.get("embedding") or {}
        if "value" in emb_obj:
            emb = emb_obj["value"]
        elif "values" in emb_obj:
            emb = emb_obj["values"]
        else:
            # defensive: try known shapes
            if "result" in data and "embedding" in data["result"]:
                emb = data["result"]["embedding"].get("values") or data["result"]["embedding"].get("value")
        if emb is None:
            raise RuntimeError(f"unexpected embedding response shape: {data}")
        embeddings.append(list(emb))
    return embeddings

def extract_text_from_gemini(data):
    """
    Robust parser for Gemini 2.x and fallback patterns.
    """

    # NEW Gemini 2.x format (your response):
    # data["candidates"][0]["content"]["parts"][0]["text"]
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass

    # Alternative structures (Gemini 1.x)
    try:
        return data["candidates"][0]["content"][0]["parts"][0]["text"]
    except Exception:
        pass

    try:
        return data["candidates"][0]["output"][0]["content"][0]["text"]
    except Exception:
        pass

    # Deep scan fallback
    def deep(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "text" and isinstance(v, str):
                    return v
                out = deep(v)
                if out:
                    return out
        elif isinstance(o, list):
            for item in o:
                out = deep(item)
                if out:
                    return out
        return None

    return deep(data) or ""


def call_gemini_chat(prompt: str, temperature: float = 0.0, max_output_tokens: int = 300):
    """
    Non-streaming call to Gemini 2.x models via :generateContent.
    Returns (answer_text, metadata)
    """

    if not API_KEY:
        raise RuntimeError("Gemini API key missing")

    url = f"{API_URL_ROOT.rstrip('/')}/v1beta/models/{LLM_MODEL}:generateContent?key={API_KEY}"

    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": float(temperature),
            "maxOutputTokens": int(max_output_tokens),
        }
    }

    resp = requests.post(url, json=body, timeout=60)

    if resp.status_code != 200:
        logger.error("Gemini error %s: %s", resp.status_code, resp.text)
        raise Exception(f"Gemini error {resp.status_code}: {resp.text}")

    data = resp.json()
    text = extract_text_from_gemini(data)

    return text, {
        "model": LLM_MODEL,
        "raw": data
    }