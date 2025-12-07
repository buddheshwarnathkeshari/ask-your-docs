from django.urls import path
from .views import UploadView, DocumentListView, DocumentDeleteView

urlpatterns = [
    path("upload/", UploadView.as_view(), name="upload"),
    path("", DocumentListView.as_view(), name="documents-list"),
    path("<uuid:doc_id>/delete/", DocumentDeleteView.as_view()),
]
