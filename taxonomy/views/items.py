from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, SAFE_METHODS

from taxonomy.models import TaxonomyItem
from taxonomy.serializers import TaxonomyItemSerializer


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
