from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from taxonomy.models import TaxonomyItem
from taxonomy.serializers import TaxonomyItemSerializer


class GenreViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TaxonomyItem.objects.filter(type=TaxonomyItem.TypeChoices.GENRE).order_by('name')
    serializer_class = TaxonomyItemSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = None
