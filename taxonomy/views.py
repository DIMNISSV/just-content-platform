from django.db.models import Count
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import TaxonomyItem, RawTerm, RawTermMapping
from .serializers import TaxonomyItemSerializer, RawTermSerializer, RawTermMappingSerializer
from .services import sync_taxonomy_presets


class TaxonomyItemViewSet(viewsets.ModelViewSet):
    queryset = TaxonomyItem.objects.all()
    serializer_class = TaxonomyItemSerializer
    permission_classes = [IsAdminUser]
    pagination_class = None


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


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_sync_presets(request):
    """
    Endpoint for admins to manually trigger the JSON preset synchronization.
    """
    result = sync_taxonomy_presets()
    if result['status'] == 'success':
        return Response(result, status=status.HTTP_200_OK)
    return Response(result, status=status.HTTP_400_BAD_REQUEST)
