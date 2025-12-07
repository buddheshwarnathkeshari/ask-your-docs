# backend/projects/urls.py
from django.urls import path
from .views import ProjectListCreateView, ProjectDetailView

urlpatterns = [
    path("", ProjectListCreateView.as_view(), name="projects-list-create"),
    path("<uuid:pk>/", ProjectDetailView.as_view(), name="projects-detail"),
]
