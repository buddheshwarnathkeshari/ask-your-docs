# URL patterns for the app
from django.urls import path
from .views import ConversationCreateView, ChatMessageView, ConversationMessagesView  # noqa: F401

urlpatterns = [
    path("", ConversationCreateView.as_view(), name="conversations-create"),  # POST -> create conversation
    path("<uuid:conv_id>/message/", ChatMessageView.as_view(), name="chat-message"),  # POST -> send message
    path("<uuid:conv_id>/messages/", ConversationMessagesView.as_view(), name="conversation-messages"),  # GET -> list messages
]
