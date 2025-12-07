# backend/projects/admin.py
from django.contrib import admin
from .models import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("id","name","owner","created_at")
    search_fields = ("name","owner__username")
