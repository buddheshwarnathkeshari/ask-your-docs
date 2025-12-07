from django.db import models
import uuid
from django.utils import timezone

class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=512)
    sha256 = models.CharField(max_length=64, db_index=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=32, default="pending")
    size = models.BigIntegerField(null=True)
    metadata = models.JSONField(default=dict)
    def __str__(self):
        return f"{self.filename} ({self.id})"

class DocumentChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey("documents.Document", on_delete=models.CASCADE, related_name="chunks")
    text = models.TextField()
    page = models.IntegerField(null=True, blank=True)
    chunk_index = models.IntegerField(default=0)
    token_count = models.IntegerField(null=True, blank=True)
    chunk_hash = models.CharField(max_length=64, db_index=True)#, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("document", "page", "chunk_index")
        indexes = [
            models.Index(fields=["chunk_hash"]),
            models.Index(fields=["document", "page"]),
        ]

    def __str__(self):
        return f"Chunk {self.id} doc={self.document_id} page={self.page} idx={self.chunk_index}"
