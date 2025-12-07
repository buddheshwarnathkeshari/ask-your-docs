# backend/projects/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Project
from .serializers import ProjectSerializer

class ProjectListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # adjust as needed

    def get(self, request):
        qs = Project.objects.filter(owner=request.user) if request.user.is_authenticated else Project.objects.none()
        serializer = ProjectSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        data['owner'] = request.user.id if request.user.is_authenticated else None
        serializer = ProjectSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
