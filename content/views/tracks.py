from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAdminUser

from content.models import TrackGroup, AdditionalTrack


class TrackGroupViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = TrackGroup.objects.all()
    permission_classes = [IsAdminUser]


class AdditionalTrackViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = AdditionalTrack.objects.all()
    permission_classes = [IsAdminUser]
