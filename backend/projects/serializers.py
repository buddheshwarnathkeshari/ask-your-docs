# backend/projects/serializers.py
from rest_framework import serializers
from .models import Project
from conversations.serializers import ConversationSerializer

class ProjectSerializer(serializers.ModelSerializer):
    conversations = ConversationSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ( "id", "name", "description", "created_at", "last_interacted_at", "conversations",)
        read_only_fields = ( "id", "created_at", "last_interacted_at", "conversations",)