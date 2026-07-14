from django.db.models import Count
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, SAFE_METHODS
from rest_framework.response import Response

from .models import TaxonomyItem, RawTerm, RawTermMapping
from .serializers import TaxonomyItemSerializer, RawTermSerializer, RawTermMappingSerializer
from .services import sync_taxonomy_presets


class IsAdminOrReadOnly(IsAdminUser):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().has_permission(request, view)


class TaxonomyItemViewSet(viewsets.ModelViewSet):
    queryset = TaxonomyItem.objects.all()
    serializer_class = TaxonomyItemSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        item_type = self.request.query_params.get('type')
        parent_id = self.request.query_params.get('parent_id')
        parent_slug = self.request.query_params.get('parent_slug')
        is_root = self.request.query_params.get('is_root')

        if item_type:
            qs = qs.filter(type=item_type)
        if parent_id:
            qs = qs.filter(parent_id=parent_id)
        if parent_slug:
            qs = qs.filter(parent__slug=parent_slug)

        if is_root == 'true':
            qs = qs.filter(parent__isnull=True)
        elif is_root == 'false':
            qs = qs.filter(parent__isnull=False)

        return qs


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
