# backend/projects/urls.py
from django.urls import path
from .views import ProjectListCreateView, ProjectDetailView, ProjectDeleteView

urlpatterns = [
    path("", ProjectListCreateView.as_view(), name="projects-list-create"),
    path("<uuid:pk>/", ProjectDetailView.as_view(), name="projects-detail"),
    path("<uuid:project_id>/delete/", ProjectDeleteView.as_view()),
]
