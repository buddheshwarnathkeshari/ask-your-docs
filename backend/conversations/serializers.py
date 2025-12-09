from rest_framework import serializers
from .models import Conversation, Project

class ConversationSerializer(serializers.ModelSerializer):
    # project_id used for both read + write
    project_id = serializers.PrimaryKeyRelatedField(
        source="project",
        queryset=Project.objects.all(),
        write_only=True,
    )

    class Meta:
        model = Conversation
        fields = ("id", "title", "project_id", "created_at")
        read_only_fields = ("id", "created_at")