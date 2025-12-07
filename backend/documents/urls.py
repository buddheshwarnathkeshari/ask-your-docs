from django.urls import path
from .views import UploadView, DocumentListView

urlpatterns = [
    path("upload/", UploadView.as_view(), name="upload"),
    path("", DocumentListView.as_view(), name="documents-list"),
]
