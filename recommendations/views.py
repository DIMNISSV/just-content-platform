from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from content.serializers import TitleSerializer
from recommendations.services.scorer import get_recommendations
from recommendations.services.velocity import get_trending_titles
from recommendations.services.merger import merge_guest_profile


class RecommendationsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Отдает персонализированные рекомендации.
        Поддерживает авторизованных пользователей и гостей (через guest_id).
        """
        user = request.user if request.user.is_authenticated else None
        guest_id = request.query_params.get('guest_id')
        limit = int(request.query_params.get('limit', 12))

        titles = get_recommendations(user=user, guest_id=guest_id, limit=limit)

        serializer = TitleSerializer(titles, many=True, context={'request': request})
        return Response(serializer.data)


class TrendingAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Отдает список произведений "В тренде", основываясь на динамике просмотров из Redis.
        """
        limit = int(request.query_params.get('limit', 12))
        titles = get_trending_titles(limit=limit)

        serializer = TitleSerializer(titles, many=True, context={'request': request})
        return Response(serializer.data)


class MergeGuestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Merges guest history into the current authenticated user's account.
        Expects 'guest_id' in the request body.
        """
        guest_id = request.data.get('guest_id')
        if not guest_id:
            return Response({"error": "guest_id is required"}, status=400)

        try:
            count = merge_guest_profile(user=request.user, guest_id=guest_id)
            return Response({
                "status": "success",
                "merged_records": count,
                "message": "Guest history has been successfully merged."
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)
