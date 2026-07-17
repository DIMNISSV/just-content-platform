from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from content.models import Title
from content.serializers import TitleSerializer


class SimilarTitlesAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk=None):
        try:
            title = Title.objects.prefetch_related('taxonomy_items').get(pk=pk)
        except Title.DoesNotExist:
            return Response({"error": "Title not found"}, status=404)

        vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')
        query = SearchQuery(title.name)

        qs = Title.objects.prefetch_related('taxonomy_items').annotate(
            rank=SearchRank(vector, query)
        ).exclude(pk=title.pk).filter(rank__gte=0.05).order_by('-rank')[:10]

        if not qs.exists():
            tax_ids = title.taxonomy_items.values_list('id', flat=True)
            qs = Title.objects.prefetch_related('taxonomy_items').filter(
                taxonomy_items__in=tax_ids
            ).exclude(pk=title.pk).distinct().order_by('-rating_score')[:10]

        serializer = TitleSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)
