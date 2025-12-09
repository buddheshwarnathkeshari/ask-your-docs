# backend/projects/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Project
from .serializers import ProjectSerializer
from conversations.models import Conversation


class ProjectViewSet(viewsets.ModelViewSet):
    """
    Handles:
    GET /projects/           → list
    POST /projects/          → create (+ auto conversation)
    GET /projects/<id>/      → retrieve
    PATCH /projects/<id>/    → partial update
    PUT /projects/<id>/      → full update
    DELETE /projects/<id>/   → soft delete
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(is_deleted=False).order_by(
            "-last_interacted_at", "-created_at"
        )

    @transaction.atomic
    def perform_create(self, serializer):
        project = serializer.save()

        # Auto-create first conversation
        Conversation.objects.create(project=project)

        # Refresh so serializer includes conversation in output
        project.refresh_from_db()

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
