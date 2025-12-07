# backend/projects/views.py
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Project
from .serializers import ProjectSerializer
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

@method_decorator(csrf_exempt, name='dispatch')
class ProjectListCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        qs = Project.objects.filter(is_deleted=False).order_by("-last_interacted_at", "-created_at").all()
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

class ProjectDeleteView(APIView):
    permission_classes = [permissions.AllowAny]

    def delete(self, request, project_id):
        p = get_object_or_404(Project, id=project_id)
        p.is_deleted = True
        p.save(update_fields=["is_deleted"])
        return Response({"deleted": True})


@method_decorator(csrf_exempt, name='dispatch')
class ProjectDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get_object(self, pk):
        try:
            return Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            return None

    def get(self, request, pk):
        proj = self.get_object(pk)
        if not proj:
            return Response({"detail":"Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectSerializer(proj).data)

    def patch(self, request, pk):
        proj = self.get_object(pk)
        if not proj:
            return Response({"detail":"Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProjectSerializer(proj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        return self.patch(request, pk)
