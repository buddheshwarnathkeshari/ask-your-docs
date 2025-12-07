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
    Replace bracketed tokens that contain SOURCE entries.
    Handles forms like:
      [SOURCE:1 PAGE:1]
      [SOURCE:1 PAGE:1, SOURCE:2 PAGE:1, SOURCE:3 PAGE:1]
    Replacement: '[DocTitle1, DocTitle2]' (no page numbers).
    Falls back to 'source:n' if doc title cannot be resolved.
    """

    if not answer_text:
        return answer_text

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
                titles[str(d.id)] = getattr(d, "filename", None) or getattr(d, "title", None) or str(d.id)
        except Exception:
            # don't fail replacement if DB lookup fails
            pass

    # Pattern to find any [...] block that contains the word SOURCE (catch multi-source brackets)
    bracket_pattern = re.compile(r"\[([^\]]*SOURCE[^\]]*)\]", flags=re.IGNORECASE)

    def bracket_repl(match):
        inner = match.group(1)
        # find all source indices inside the bracket, e.g. SOURCE:1 or SOURCE : 2
        idxs = re.findall(r"SOURCE\s*:\s*(\d+)", inner, flags=re.IGNORECASE)
        if not idxs:
            return ""  # remove odd bracket without numeric sources

        # keep unique indices in order
        seen = set()
        unique_idxs = []
        for s in idxs:
            if s not in seen:
                seen.add(s)
                unique_idxs.append(int(s))

        resolved_titles = []
        for idx in unique_idxs:
            docid = index_to_docid.get(idx)
            if docid:
                t = titles.get(str(docid)) or str(docid)
            else:
                t = f"source:{idx}"
            # shorten long title
            t = str(t)
            if len(t) > 60:
                t = t[:56].rsplit(" ", 1)[0] + "..."
            resolved_titles.append(t)

        if not resolved_titles:
            return ""  # nothing useful, remove

        # join with comma and return bracket with titles (no pages)
        return "[" + ", ".join(resolved_titles) + "]"

    # Replace bracketed SOURCE blocks first
    result = bracket_pattern.sub(bracket_repl, answer_text)

    return result


def strip_remaining_source_markers(text):
    """
    Defensive cleanup: remove any stray SOURCE tokens / leftover markers
    and normalize punctuation/spacing.
    """
    if not text:
        return text

    # Remove remaining SOURCE:... tokens anywhere (not just inside brackets)
    text = re.sub(r"SOURCE\s*:\s*\d+(\s*PAGE\s*:\s*\d+)?", "", text, flags=re.IGNORECASE)

    # Remove any empty brackets left (e.g. [] or [   ])
    text = re.sub(r"\[\s*\]", "", text)

    # Normalize repeated commas/whitespace leftover from removals
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+,\s+", ", ", text)
    text = re.sub(r"\s+\.\s+", ". ", text)
    # collapse >2 newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

def remove_inline_source_markers(answer_text, retrieved=None):
    """
    Remove inline SOURCE/PAGE markers from LLM output so assistant prose
    remains readable. Do NOT remove or modify saved citations — they are
    returned separately and rendered under 'Sources'.

    This function handles:
      - bracketed multi-source tokens like:
          [SOURCE:1 PAGE:1, SOURCE:2 PAGE:1]
      - single bracketed tokens like:
          [SOURCE:1 PAGE:1]
      - stray tokens like: SOURCE:1 PAGE:1 or SOURCE:1
    Returns cleaned text.
    """

    if not answer_text:
        return answer_text

    text = answer_text

    # 1) Remove entire bracketed blocks that contain the word SOURCE (case-insensitive).
    #    e.g. "[SOURCE:1 PAGE:1, SOURCE:2 PAGE:1]" -> ""
    text = re.sub(r"\[\s*[^\]]*?\bSOURCE\b[^\]]*?\]", "", text, flags=re.IGNORECASE)

    # 2) Remove any remaining SOURCE:NN [optional PAGE:NN] tokens occurring outside brackets:
    #    e.g. "SOURCE:1 PAGE:1" or "SOURCE : 1" -> ""
    text = re.sub(r"SOURCE\s*:\s*\d+(\s*,\s*\d+)*(\s*PAGE\s*:\s*\d+)?", "", text, flags=re.IGNORECASE)

    # 3) Defensive cleanup:
    #    - remove repeated whitespace
    #    - remove leftover punctuation sequences like ", ," or ", ." introduced by removals
    text = re.sub(r"\s{2,}", " ", text)                          # collapse multiple spaces
    text = re.sub(r",\s*,+", ",", text)                         # collapse duplicate commas
    text = re.sub(r",\s*\.", ".", text)                         # ", ." -> "."
    text = re.sub(r"\s+\.", ".", text)                          # " word ." -> " word."
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\(\s*\)", "", text)                         # remove empty parens if any
    text = re.sub(r"\[\s*\]", "", text)                         # remove empty brackets if any
    text = re.sub(r"\n{3,}", "\n\n", text)                      # collapse many newlines

    return text.strip()


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
    retrieved = search_vectors(emb, top_k=top_k, project_id=project_id)

    # 3) load last N messages from conversation (if any)
    history_qs = conversation.messages.order_by("created_at").all() if hasattr(conversation, "messages") else []
    history = [{"role": m.role, "text": m.text} for m in history_qs][-8:]

    # 4) build prompt
    prompt = make_prompt(history, retrieved, user_text)

    # 5) call LLM
    answer_text, meta = call_gemini_chat(prompt, temperature=temperature, max_output_tokens=max_output_tokens)

    # 6) post-process for human-friendly source labels
    # try:
    #     answer_text = pretty_replace_sources(answer_text, retrieved)
    # except Exception:
    #     pass

    # # final defensive cleanup
    # try:
    #     answer_text = strip_remaining_source_markers(answer_text)
    # except Exception:
    #     pass
    try:
        answer_text = remove_inline_source_markers(answer_text, retrieved)
    except Exception:
        # defensive: if cleaning fails, keep original answer_text
        pass

    return answer_text, retrieved, meta
