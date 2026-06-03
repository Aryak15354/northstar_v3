"""Alternative, sentiment, and macro signal modules."""

from .bulk_deals import compute_bulk_deal_features
from .promoter_pledge import compute_pledge_features
from .earnings_dates import compute_earnings_features, get_availability_date
from .credit_ratings import compute_rating_features
from .order_announcements import compute_announcement_features
from .signal_loader import AlternativeDataLoader
from .feature_builder import AlternativeFeatureBuilder
from .sentiment_bridge import SentimentBridge
from .sentiment_overlay import SentimentOverlay
from .news_sentiment import NewsSentimentBuilder

__all__ = [
    "compute_bulk_deal_features",
    "compute_pledge_features",
    "compute_earnings_features",
    "get_availability_date",
    "compute_rating_features",
    "compute_announcement_features",
    "AlternativeDataLoader",
    "AlternativeFeatureBuilder",
    "SentimentBridge",
    "SentimentOverlay",
    "NewsSentimentBuilder",
]
