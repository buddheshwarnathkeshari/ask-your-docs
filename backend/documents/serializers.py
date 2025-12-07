from rest_framework import serializers
from .models import Document

class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()

class DocumentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ("id", "filename", "sha256", "size", "status", "uploaded_at")