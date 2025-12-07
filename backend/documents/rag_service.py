# backend/documents/rag_service.py
from .gemini_client import gemini_embed_batch, call_gemini_chat
from .qdrant_search import search_vectors
from documents.models import DocumentChunk, Document
from django.db import transaction
import textwrap
import re

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


def pretty_replace_sources(answer_text, retrieved):
    """
    Replace occurrences like "[SOURCE:3 PAGE:1]" with readable string
    using retrieved list (index -> payload/document id).
    Format example: "[Refunds_policy.pdf ▪ page 1]"
    If we cannot resolve a doc title, fallback to the document id.
    """

    # Build mapping index -> document id and try to resolve titles from Document table
    index_to_docid = {}
    doc_ids = set()
    for idx, r in enumerate(retrieved, start=1):
        p = r.get("payload", {}) or {}
        doc_id = p.get("document_id") or p.get("document")
        index_to_docid[idx] = str(doc_id) if doc_id is not None else None
        if doc_id:
            doc_ids.add(str(doc_id))

    # fetch titles for any doc ids we can
    titles = {}
    if doc_ids:
        try:
            docs = Document.objects.filter(id__in=doc_ids)
            for d in docs:
                # prefer filename or title field if available
                titles[str(d.id)] = getattr(d, "filename", None) or getattr(d, "title", None) or str(d.id)
        except Exception:
            # defensive: don't fail replacement if DB lookup fails
            pass

    # regex to find [SOURCE:n PAGE:p] with optional whitespace
    patt = re.compile(r"\[SOURCE\s*:\s*(\d+)\s+PAGE\s*:\s*(\d+)\]", flags=re.IGNORECASE)

    def repl(match):
        idx = int(match.group(1))
        page = match.group(2)
        docid = index_to_docid.get(idx)
        title = None
        if docid:
            title = titles.get(str(docid)) or docid
        else:
            title = f"source:{idx}"
        # short and safe title (trim if too long)
        if len(title) > 40:
            title_short = title[:36].rsplit(" ", 1)[0] + "..."
        else:
            title_short = title
        return f"[{title_short}]"

    return patt.sub(repl, answer_text)


def answer_query(conversation, user_text, top_k=6, temperature=0.0, max_output_tokens=300):
    """
    conversation: Conversation model instance (Django ORM)
    user_text: str
    Returns: answer_text, retrieved (list), meta (dict)
    """
    # 1) embed query
    emb = gemini_embed_batch([user_text])[0]

    # 2) search qdrant
    project_id = getattr(conversation, "project_id", None) or (getattr(conversation, "project", None) and str(conversation.project.id))
    retrieved = search_vectors(emb, top_k=top_k)

    # 3) load last N messages from conversation (if any)
    history_qs = conversation.messages.order_by("created_at").all() if hasattr(conversation, "messages") else []
    history = [{"role": m.role, "text": m.text} for m in history_qs][-8:]

    # 4) build prompt
    prompt = make_prompt(history, retrieved, user_text)

    # 5) call LLM
    answer_text, meta = call_gemini_chat(prompt, temperature=temperature, max_output_tokens=max_output_tokens)

    # 6) post-process for human-friendly source labels
    try:
        answer_text = pretty_replace_sources(answer_text, retrieved)
    except Exception:
        # be defensive: if replacement fails, keep original answer
        pass

    return answer_text, retrieved, meta
