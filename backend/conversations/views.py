import logging
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction 
from documents.models import Document
from rest_framework.generics import CreateAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from projects.models import Project
from .models import Conversation, Message, MessageCitation
from documents.rag_service import answer_query
from .serializers import ConversationSerializer
logger = logging.getLogger(__name__)


class ConversationCreateView(CreateAPIView):
    serializer_class = ConversationSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        conversation = serializer.save()

        # Update the parent project's last interaction timestamp
        Project.objects.filter(pk=conversation.project_id).update(
            last_interacted_at=timezone.now()
        )

class ChatMessageView(APIView):

    @transaction.atomic
    def post(self, request, conv_id):
        try:
            conv = get_object_or_404(Conversation, id=conv_id)

            # touch project early so UI sorts it to top quickly
            Project.objects.filter(pk=conv.project_id).update(
                last_interacted_at=timezone.now()
            )

            user_text = (request.data.get("text") or "").strip()
            if not user_text:
                return Response({"detail": "text required"}, status=status.HTTP_400_BAD_REQUEST)

            # save user message
            user_msg = Message.objects.create(conversation=conv, role="user", text=user_text)

            # --- NEW: if conversation has a project but no documents, return friendly prompt ---
            # This prevents the RAG pipeline from running when there's nothing to search.
            if getattr(conv, "project", None):
                docs_count = Document.objects.filter(project_id=str(conv.project.id), is_deleted=False).count()
                if docs_count == 0:
                    # create assistant message and return immediately
                    assistant_text = "Please add a document first to ask questions about this project."
                    assistant_msg = Message.objects.create(
                        conversation=conv,
                        role="assistant",
                        text=assistant_text,
                        model=None
                    )

                    # no citations to persist
                    return Response({"answer": assistant_msg.text, "citations": []})

            # call rag service
            try:
                answer_text, retrieved, meta = answer_query(conv, user_text, top_k=6)
            except Exception as exc:
                # Detect Vertex/Gen AI resource exhausted response
                msg_text = "The AI service is temporarily overloaded or out of quota. Please try again in a few moments."
                logger.exception("RAG / LLM call failed: %s", exc)

                # create assistant message so frontend shows friendly reply
                assistant_msg = Message.objects.create(
                    conversation=conv,
                    role="assistant",
                    text=msg_text,
                    model=None
                )

                return Response({"answer": assistant_msg.text, "citations": []})

            # save assistant message
            assistant_msg = Message.objects.create(
                conversation=conv,
                role="assistant",
                text=answer_text,
                model=meta.get("model")
            )

            # persist citations (defensive). retrieved is the list returned by the vector search (payloads).
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
            Project.objects.filter(pk=conv.project_id).update(
                last_interacted_at=timezone.now()
            )

            # Build a mapping of document_id -> human-friendly title (if available)
            doc_ids = []
            for c in assistant_msg.citations.all():
                if c.document_id:
                    doc_ids.append(str(c.document_id))

            doc_title_map = {}
            if doc_ids:
                try:
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
            # log full traceback server-side and return JSON
            logger.exception("Error in ChatMessageView")
            if getattr(__import__("django.conf").conf.settings, "DEBUG", False):
                # include error string when DEBUG
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
