from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from content.models import Episode
from content.serializers import EpisodeSerializer


class EpisodeViewSet(viewsets.ModelViewSet):
    queryset = Episode.objects.all()
    serializer_class = EpisodeSerializer
    permission_classes = [IsAdminUser]
