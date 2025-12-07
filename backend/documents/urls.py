from django.urls import path
from .views import UploadView, DocumentListView, DocumentDeleteView, DocumentDownloadView

urlpatterns = [
    path("upload/", UploadView.as_view(), name="upload"),
    path("", DocumentListView.as_view(), name="documents-list"),
    path("<uuid:doc_id>/delete/", DocumentDeleteView.as_view()),
    path("<uuid:doc_id>/download/", DocumentDownloadView.as_view(), name="document-download"),
]
