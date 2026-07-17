from .merge import MergeGuestAPIView
from .recommendations import RecommendationsAPIView
from .trending import TrendingAPIView
from .similar import SimilarTitlesAPIView

__all__ = (
    'RecommendationsAPIView',
    'TrendingAPIView',
    'MergeGuestAPIView',
    'SimilarTitlesAPIView',
)
