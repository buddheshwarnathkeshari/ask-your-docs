# backend/conversations/models.py
import uuid
from django.db import models
from django.conf import settings

class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    ROLE_CHOICES = (("user","user"),("assistant","assistant"),("system","system"))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    model = models.CharField(max_length=200, blank=True, null=True)
    tokens = models.IntegerField(null=True, blank=True)

class MessageCitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, related_name="citations", on_delete=models.CASCADE)
    chunk_id = models.UUIDField(null=True)
    document_id = models.UUIDField(null=True)
    page = models.IntegerField(null=True)
    score = models.FloatField(null=True)
    snippet = models.TextField(null=True)
