from django.urls import path

from .views import RecommendationsAPIView

urlpatterns = [
    path('', RecommendationsAPIView.as_view(), name='smart-recommendations'),
]
