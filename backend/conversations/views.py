# backend/conversations/views.py
import logging
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Conversation, Message, MessageCitation
from documents.rag_service import answer_query

logger = logging.getLogger(__name__)


class ConversationCreateView(APIView):
    """
    POST /api/conversations/
    Payload: { project_id: <uuid> } (optional)
    Behavior:
      - If project_id provided and a Conversation already exists for that project, reuse latest conversation
        and return { id: conv_id, messages: [...] } where each message contains citations.
      - Otherwise create a new Conversation and return { id: conv_id } (201).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        project_id = request.data.get("project_id")
        project = None
        if project_id:
            try:
                from projects.models import Project
                project = Project.objects.filter(id=project_id).first()
            except Exception:
                logger.exception("Failed to load Project for id=%s", project_id)
                project = None

        # If project provided, attempt to reuse latest conversation for that project
        if project:
            conv = Conversation.objects.filter(project=project).order_by("-created_at").first()
            if conv:
                # build message list including citations so frontend can rehydrate the chat
                msgs_out = []
                try:
                    # prefetching not required but keep simple
                    for m in conv.messages.order_by("created_at").all():
                        msg_obj = {
                            "id": str(m.id),
                            "role": m.role,
                            "text": m.text,
                            "created_at": m.created_at.isoformat() if getattr(m, "created_at", None) else None,
                            "model": getattr(m, "model", None),
                            "citations": []
                        }
                        # include citations for assistant messages (if any)
                        try:
                            for c in m.citations.all():
                                doc_title = None
                                if c.document_id:
                                    # lazy import Document to find human friendly name
                                    from documents.models import Document
                                    try:
                                        d = Document.objects.filter(id=c.document_id).first()
                                        if d:
                                            doc_title = getattr(d, "filename", None) or getattr(d, "title", None) or str(d.id)
                                    except Exception:
                                        logger.exception("Failed to fetch document for citation: %s", c.document_id)
                                msg_obj["citations"].append({
                                    "chunk_id": c.chunk_id,
                                    "document_id": c.document_id,
                                    "document_title": doc_title or (str(c.document_id) if c.document_id else None),
                                    "page": c.page,
                                    "score": c.score,
                                    "snippet": c.snippet,
                                })
                        except Exception:
                            logger.exception("Failed to enumerate citations for message %s", getattr(m, "id", None))
                        msgs_out.append(msg_obj)
                except Exception:
                    logger.exception("Failed to build messages payload for conversation %s", getattr(conv, "id", None))

                # update project's last_interacted_at so it floats to top
                try:
                    if hasattr(project, "touch") and callable(project.touch):
                        project.touch()
                    else:
                        project.last_interacted_at = timezone.now()
                        project.save(update_fields=["last_interacted_at"])
                except Exception:
                    logger.exception("Failed to touch project.last_interacted_at")

                return Response({"id": str(conv.id), "messages": msgs_out})

        # Otherwise create a new conversation
        try:
            conv = Conversation.objects.create(owner=request.user if request.user.is_authenticated else None, project=project)
        except Exception as exc:
            logger.exception("Failed to create conversation")
            return Response({"detail": "failed to create conversation"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # touch project last_interacted_at if project available
        if project:
            try:
                if hasattr(project, "touch") and callable(project.touch):
                    project.touch()
                else:
                    project.last_interacted_at = timezone.now()
                    project.save(update_fields=["last_interacted_at"])
            except Exception:
                logger.exception("Failed to touch project.last_interacted_at after conversation create")

        return Response({"id": str(conv.id)}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class ChatMessageView(APIView):
    """
    POST /api/conversations/<conv_id>/message/
    Body: { text: "..." }
    Returns: { answer: "...", citations: [...] }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, conv_id):
        try:
            conv = get_object_or_404(Conversation, id=conv_id)

            # touch project early so UI sorts it to top quickly
            if conv.project:
                try:
                    if hasattr(conv.project, "touch") and callable(conv.project.touch):
                        conv.project.touch()
                    else:
                        conv.project.last_interacted_at = timezone.now()
                        conv.project.save(update_fields=["last_interacted_at"])
                except Exception:
                    logger.exception("Failed to update project.last_interacted_at (early)")

            user_text = (request.data.get("text") or "").strip()
            if not user_text:
                return Response({"detail": "text required"}, status=status.HTTP_400_BAD_REQUEST)

            # save user message
            user_msg = Message.objects.create(conversation=conv, role="user", text=user_text)

            # call rag service
            answer_text, retrieved, meta = answer_query(conv, user_text, top_k=6)

            # save assistant message
            assistant_msg = Message.objects.create(
                conversation=conv,
                role="assistant",
                text=answer_text,
                model=meta.get("model")
            )

            # persist citations (retrieved is the vector search payload)
            for r in retrieved:
                p = r.get("payload", {}) or {}
                try:
                    MessageCitation.objects.create(
                        message=assistant_msg,
                        chunk_id=p.get("chunk_id") or p.get("id"),
                        document_id=p.get("document_id") or p.get("document"),
                        page=p.get("page"),
                        score=r.get("score"),
                        snippet=(p.get("text") or p.get("chunk_text") or p.get("text_snippet") or "")[:2000]
                    )
                except Exception:
                    logger.exception("Failed to save citation for payload: %s", p)

            # touch project last_interacted_at so it floats to top (defensive)
            try:
                if getattr(conv, "project", None):
                    if hasattr(conv.project, "touch") and callable(conv.project.touch):
                        conv.project.touch()
                    else:
                        conv.project.last_interacted_at = timezone.now()
                        conv.project.save(update_fields=["last_interacted_at"])
            except Exception:
                logger.exception("Failed to touch project.last_interacted_at on message")

            # Build a mapping of document_id -> human-friendly title (if available)
            doc_ids = []
            for c in assistant_msg.citations.all():
                if c.document_id:
                    doc_ids.append(str(c.document_id))

            doc_title_map = {}
            if doc_ids:
                try:
                    from documents.models import Document
                    docs = Document.objects.filter(id__in=doc_ids)
                    for d in docs:
                        doc_title_map[str(d.id)] = getattr(d, "filename", None) or getattr(d, "title", None) or str(d.id)
                except Exception:
                    logger.exception("Failed to load Document titles for citations")

            # prepare citation objects for API response
            citations = []
            for idx, c in enumerate(assistant_msg.citations.all()):
                doc_title = None
                if c.document_id:
                    doc_title = doc_title_map.get(str(c.document_id)) or str(c.document_id)
                citations.append({
                    "index": idx + 1,
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "document_title": doc_title,
                    "page": c.page,
                    "score": c.score,
                    "snippet": c.snippet
                })

            return Response({"answer": assistant_msg.text, "citations": citations})
        except Exception as exc:
            logger.exception("Error in ChatMessageView")
            if getattr(__import__("django.conf").conf.settings, "DEBUG", False):
                return Response({"detail": "internal error", "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"detail": "internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConversationMessagesView(APIView):
    """
    GET /api/conversations/<conv_id>/messages/
    Returns a list of messages for the conversation. Each message includes
    an array `citations` (empty for non-assistant messages). Each citation
    contains chunk_id, document_id, document_title (human friendly), page,
    score, snippet.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, conv_id):
        try:
            conv = get_object_or_404(Conversation, id=conv_id)

            # load all messages in chronological order
            msgs_qs = conv.messages.order_by("created_at").all()

            # gather document ids referenced in citations to fetch titles
            doc_ids = set()
            for m in msgs_qs:
                for c in getattr(m, "citations").all():
                    if c.document_id:
                        doc_ids.add(str(c.document_id))

            # build map document_id -> human-friendly title (filename/title fallback)
            doc_title_map = {}
            if doc_ids:
                try:
                    from documents.models import Document
                    docs = Document.objects.filter(id__in=list(doc_ids))
                    for d in docs:
                        doc_title_map[str(d.id)] = getattr(d, "filename", None) or getattr(d, "title", None) or str(d.id)
                except Exception:
                    logger.exception("Failed to load document titles for conversation messages")

            # compose response messages
            out = []
            for m in msgs_qs:
                message_obj = {
                    "id": str(m.id),
                    "role": m.role,
                    "text": m.text,
                    "created_at": m.created_at.isoformat() if getattr(m, "created_at", None) else None,
                    "model": getattr(m, "model", None),
                    "citations": []
                }

                # include citations (if any) with human readable document_title
                try:
                    for c in m.citations.all():
                        doc_id_str = str(c.document_id) if c.document_id else None
                        doc_title = doc_title_map.get(doc_id_str) if doc_id_str else None
                        message_obj["citations"].append({
                            "chunk_id": c.chunk_id,
                            "document_id": c.document_id,
                            "document_title": doc_title or (str(c.document_id) if c.document_id else None),
                            "page": c.page,
                            "score": c.score,
                            "snippet": c.snippet,
                        })
                except Exception:
                    logger.exception("Failed to enumerate citations for message %s", getattr(m, "id", "<unknown>"))

                out.append(message_obj)

            return Response(out)
        except Exception as exc:
            logger.exception("Error in ConversationMessagesView")
            return Response({"detail": "internal error", "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
