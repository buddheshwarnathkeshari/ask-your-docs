from django.contrib import admin
from .models import Document, DocumentChunk

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "filename", "sha256", "status", "uploaded_at")



@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "document", "page", "chunk_index", "token_count", "created_at")
    search_fields = ("chunk_hash", "text")
    list_filter = ("page",)