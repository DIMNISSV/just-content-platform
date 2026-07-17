from django.urls import path

from .views import RecommendationsAPIView, TrendingAPIView

urlpatterns = [
    path('', RecommendationsAPIView.as_view(), name='smart-recommendations'),
    path('trending/', TrendingAPIView.as_view(), name='trending-recommendations'),
]
