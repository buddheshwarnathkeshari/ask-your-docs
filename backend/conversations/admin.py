# backend/conversations/admin.py
from django.contrib import admin
from .models import Conversation, Message, MessageCitation

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "owner", "created_at")
    list_filter = ("created_at", "owner")
    search_fields = ("id", "title", "owner__username")
    readonly_fields = ("created_at",)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "created_at", "model", "tokens")
    list_filter = ("role", "created_at")
    search_fields = ("id", "text", "conversation__id")
    readonly_fields = ("created_at",)

@admin.register(MessageCitation)
class MessageCitationAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "chunk_id", "document_id", "page", "score")
    search_fields = ("chunk_id", "document_id", "message__id", "snippet")
    readonly_fields = ()
    list_filter = ("page",)

# optional: register inline view of messages inside a conversation
class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("id", "role", "text", "created_at", "model", "tokens")
    can_delete = False
    show_change_link = True

ConversationAdmin.inlines = [MessageInline]
