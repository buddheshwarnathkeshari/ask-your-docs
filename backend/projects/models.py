# backend/projects/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_interacted_at = models.DateTimeField(null=True, blank=True, default=timezone.now)
    is_deleted = models.BooleanField(default=False)

    def update_last_interacted_at(self, last_interacted_at=timezone.now(), save=True):
        self.last_interacted_at = last_interacted_at
        if save:
            self.save(update_fields=["last_interacted_at"])

    def __str__(self):
        return self.name
