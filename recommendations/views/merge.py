from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from recommendations.services.merger import merge_guest_profile


class MergeGuestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
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
