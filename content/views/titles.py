from django.db.models import Exists, OuterRef, Value, BooleanField
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from content.models import Title, Favorite, TitleRating
from content.serializers import TitleSerializer, TitleDetailSerializer
from content.services.search_builder import parse_ast_to_q


class TitleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Title.objects.all().order_by('-created_at')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'original_name']
    ordering_fields = ['created_at', 'rating_score', 'release_year']
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related('taxonomy_items')
        user = self.request.user

        if user.is_authenticated:
            favorite_subquery = Favorite.objects.filter(user=user, title=OuterRef('pk'))
            qs = qs.annotate(is_favorite_annotation=Exists(favorite_subquery))
        else:
            qs = qs.annotate(is_favorite_annotation=Value(False))

        c_type = self.request.query_params.get('type')
        genre = self.request.query_params.get('genre')
        tax_items = self.request.query_params.get('taxonomy_items')
        tax_items_any = self.request.query_params.get('taxonomy_items_any')

        if c_type in [Title.Type.MOVIE, Title.Type.SERIES]:
            qs = qs.filter(type=c_type)
        if genre:
            qs = qs.filter(taxonomy_items__slug=genre)

        if tax_items:
            slugs = tax_items.split(',')
            for slug in slugs:
                qs = qs.filter(taxonomy_items__slug=slug.strip())

        if tax_items_any:
            slugs = [s.strip() for s in tax_items_any.split(',')]
            qs = qs.filter(taxonomy_items__slug__in=slugs).distinct()

        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticatedOrReadOnly])
    def advanced_search(self, request):
        ast = request.data.get('query')
        if not ast:
            return Response({"error": "No query provided"}, status=status.HTTP_400_BAD_REQUEST)

        q_obj = parse_ast_to_q(ast)
        qs = self.get_queryset().filter(q_obj).distinct()

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='toggle-favorite')
    def toggle_favorite(self, request, pk=None):
        title = self.get_object()
        fav, created = Favorite.objects.get_or_create(user=request.user, title=title)
        if not created:
            fav.delete()
            return Response({"status": "removed", "is_favorite": False})
        return Response({"status": "added", "is_favorite": True})

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def favorites(self, request):
        fav_titles = Title.objects.filter(favorited_by__user=request.user).order_by('-favorited_by__created_at')
        fav_titles = fav_titles.annotate(is_favorite_annotation=Value(True, output_field=BooleanField()))
        page = self.paginate_queryset(fav_titles)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(fav_titles, many=True)
        return Response(serializer.data)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TitleDetailSerializer
        return TitleSerializer

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def rate(self, request, pk=None):
        title = self.get_object()
        score = request.data.get('score')
        if not score or not isinstance(score, int) or not (1 <= score <= 10):
            return Response({"error": "Score must be an integer between 1 and 10"}, status=status.HTTP_400_BAD_REQUEST)
        TitleRating.objects.update_or_create(
            user=request.user,
            title=title,
            defaults={'score': score}
        )
        title.refresh_from_db()
        return Response({"status": "rated", "new_score": title.rating_score, "votes": title.votes_count})
