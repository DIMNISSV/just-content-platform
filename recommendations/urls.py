from django.urls import path
from .views import RecommendationsAPIView, TrendingAPIView, MergeGuestAPIView, SimilarTitlesAPIView

urlpatterns = [
    path('', RecommendationsAPIView.as_view(), name='smart-recommendations'),
    path('trending/', TrendingAPIView.as_view(), name='trending-recommendations'),
    path('merge-guest/', MergeGuestAPIView.as_view(), name='merge-guest-profile'),
    path('similar/<uuid:pk>/', SimilarTitlesAPIView.as_view(), name='similar-titles'),
]
