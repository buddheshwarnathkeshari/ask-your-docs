# backend/documents/rag_service.py
from .gemini_client import gemini_embed_batch, call_gemini_chat
from .qdrant_search import search_vectors
from documents.models import DocumentChunk
from django.db import transaction
import textwrap

PROMPT_SYSTEM = (
    "You are a helpful assistant. Use only the provided document snippets to answer. "
    "Every factual claim must have an inline citation of the form [SOURCE:n PAGE:p]. "
    "If information is not present in the snippets, say \"I don't know\"."
)

def build_context_snippets(retrieved):
    parts = []
    for idx, r in enumerate(retrieved, start=1):
        p = r.get("payload", {}) or {}
        chunk_id = p.get("chunk_id") or p.get("id") or r.get("id")
        doc_id = p.get("document_id") or p.get("document")
        page = p.get("page")
        # prefer full text fields, fallback to short snippet
        text = p.get("text") or p.get("chunk_text") or p.get("text_snippet") or ""
        text = textwrap.shorten(text.strip().replace("\n", " "), width=1500, placeholder=" ...")
        parts.append(f"[{idx}] CHUNK_ID:{chunk_id} DOC:{doc_id} PAGE:{page}\n{text}")
    return "\n\n".join(parts)

def make_prompt(history_messages, retrieved, user_query):
    # history_messages: list of dicts {"role","text"} (last N)
    history_text = "\n".join([f"{h['role'].upper()}: {h['text']}" for h in history_messages[-8:]])
    retrieved_text = build_context_snippets(retrieved)
    prompt = (
        PROMPT_SYSTEM + "\n\n" +
        "CONTEXT SNIPPETS:\n" + retrieved_text + "\n\n" +
        "CHAT HISTORY:\n" + history_text + "\n\n" +
        "USER: " + user_query + "\n\n" +
        "Answer concisely and put inline citations for claims like [SOURCE:1 PAGE:3]."
    )
    return prompt

def answer_query(conversation, user_text, top_k=6, temperature=0.0, max_output_tokens=300):
    """
    conversation: Conversation model instance (Django ORM)
    user_text: str
    Returns: answer_text, retrieved (list), meta (dict)
    """
    # 1) embed query
    emb = gemini_embed_batch([user_text])[0]

    # 2) search qdrant
    retrieved = search_vectors(emb, top_k=top_k)

    # 3) load last N messages from conversation (if any)
    history_qs = conversation.messages.order_by("created_at").all() if hasattr(conversation, "messages") else []
    history = [{"role": m.role, "text": m.text} for m in history_qs][-8:]

    # 4) build prompt
    prompt = make_prompt(history, retrieved, user_text)

    # 5) call LLM
    answer_text, meta = call_gemini_chat(prompt, temperature=temperature, max_output_tokens=max_output_tokens)

    return answer_text, retrieved, meta
