# backend/conversations/views.py
import logging
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Conversation, Message, MessageCitation
from documents.rag_service import answer_query

logger = logging.getLogger(__name__)

class ConversationCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        conv = Conversation.objects.create(owner=request.user if request.user.is_authenticated else None)
        return Response({"id": str(conv.id)}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class ChatMessageView(APIView):
    permission_classes = [permissions.AllowAny]  # relax for local testing

    def post(self, request, conv_id):
        try:
            conv = get_object_or_404(Conversation, id=conv_id)
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

            # persist citations (defensive)
            for r in retrieved:
                p = r.get("payload", {}) or {}
                try:
                    MessageCitation.objects.create(
                        message=assistant_msg,
                        chunk_id=p.get("chunk_id") or p.get("id"),
                        document_id=p.get("document_id") or p.get("document"),
                        page=p.get("page"),
                        score=r.get("score"),
                        snippet=(p.get("text") or p.get("chunk_text") or "")[:2000]
                    )
                except Exception:
                    logger.exception("Failed to save citation for payload: %s", p)

            citations = [
                {
                    "index": idx + 1,
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "page": c.page,
                    "score": c.score,
                    "snippet": c.snippet
                }
                for idx, c in enumerate(assistant_msg.citations.all())
            ]

            return Response({"answer": assistant_msg.text, "citations": citations})

        except Exception as exc:
            # log full traceback server-side and return JSON
            logger.exception("Error in ChatMessageView")
            if getattr(__import__("django.conf").conf.settings, "DEBUG", False):
                # include error string when DEBUG
                return Response({"detail": "internal error", "error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"detail": "internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
