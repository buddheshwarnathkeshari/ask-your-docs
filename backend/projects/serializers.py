# backend/projects/serializers.py
from rest_framework import serializers
from .models import Project

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ("id","name","description","owner","created_at","last_interacted_at")
        read_only_fields = ("id","created_at","owner","last_interacted_at")
