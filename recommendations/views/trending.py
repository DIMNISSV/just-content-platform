from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from content.serializers import TitleSerializer
from recommendations.services.velocity import get_trending_titles


class TrendingAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        limit = int(request.query_params.get('limit', 12))
        titles = get_trending_titles(limit=limit)

        serializer = TitleSerializer(titles, many=True, context={'request': request})
        return Response(serializer.data)
