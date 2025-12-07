# backend/documents/admin.py
from django.contrib import admin
from .models import Document, DocumentChunk

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "filename", "project", "sha256", "status", "uploaded_at")
    list_filter = ("status", "project")
    search_fields = ("filename", "sha256")

@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "project", "page", "chunk_index", "token_count", "created_at")
    search_fields = ("chunk_hash", "text")
    list_filter = ("page", "project")
