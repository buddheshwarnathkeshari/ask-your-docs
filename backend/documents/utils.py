# backend/documents/utils.py
import hashlib
from typing import List, Tuple
import fitz  # PyMuPDF
import math

# Simple token estimator: 1 token ~= 0.75 words (approx). Good enough for chunking dev.
def estimate_tokens(text: str) -> int:
    words = len(text.split())
    return max(1, math.ceil(words / 0.75))

def extract_text_from_pdf(path: str) -> List[Tuple[int, str]]:
    """
    Returns list of (page_number, text) for a PDF.
    """
    docs = []
    doc = fitz.open(path)
    for i in range(doc.page_count):
        page = doc.load_page(i)
        text = page.get_text("text")
        docs.append((i + 1, text))
    doc.close()
    return docs

def chunk_text(text: str, chunk_tokens: int = 600, overlap: int = 80) -> List[str]:
    """
    Chunk the text roughly by sentences/lines until token limit.
    Very pragmatic: split by newline, accumulate until estimated tokens >= chunk_tokens.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    chunks = []
    cur = []
    cur_tokens = 0
    for line in lines:
        tkns = estimate_tokens(line)
        if cur and (cur_tokens + tkns) > chunk_tokens:
            chunks.append(" ".join(cur))
            # carry overlap lines - naive: keep last N tokens as overlap
            if overlap > 0:
                # keep last k words from current chunk as starting point for next
                last_words = " ".join(" ".join(cur).split()[-overlap:])
                cur = [last_words] if last_words else []
                cur_tokens = estimate_tokens(last_words)
            else:
                cur = []
                cur_tokens = 0
        cur.append(line)
        cur_tokens += tkns
    if cur:
        chunks.append(" ".join(cur))
    return chunks

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
