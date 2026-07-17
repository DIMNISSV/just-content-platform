from django.db.models import Count
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser

from taxonomy.models import RawTerm, RawTermMapping
from taxonomy.serializers import RawTermSerializer, RawTermMappingSerializer


class RawTermViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RawTerm.objects.all()
    serializer_class = RawTermSerializer
    permission_classes = [IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        mapped = self.request.query_params.get('mapped')

        if mapped == 'true':
            qs = qs.annotate(mapping_count=Count('mappings')).filter(mapping_count__gt=0)
        elif mapped == 'false':
            qs = qs.annotate(mapping_count=Count('mappings')).filter(mapping_count=0)

        return qs


class RawTermMappingViewSet(viewsets.ModelViewSet):
    queryset = RawTermMapping.objects.all()
    serializer_class = RawTermMappingSerializer
    permission_classes = [IsAdminUser]
    pagination_class = None
