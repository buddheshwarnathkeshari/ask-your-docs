from django.urls import path
from .views import ConversationCreateView, ChatMessageView

urlpatterns = [
    path("", ConversationCreateView.as_view(), name="conversations-create"),  # POST -> create conversation
    path("<uuid:conv_id>/message/", ChatMessageView.as_view(), name="chat-message"),  # POST -> send message
]
