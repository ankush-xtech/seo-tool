"""
Factory to auto-select the best available Maps provider.
If SERPAPI_KEY is set, use SerpAPI. Otherwise fall back to scraper.
"""
from app.core.config import settings
from .base_provider import BaseMapsProvider
from .serpapi_provider import SerpAPIProvider


def get_maps_provider() -> BaseMapsProvider:
    serpapi_key = getattr(settings, "SERPAPI_KEY", None)
    if serpapi_key:
        return SerpAPIProvider(api_key=serpapi_key)
    raise ValueError(
        "No Maps provider available. Set SERPAPI_KEY in your .env file. "
        "Get a free API key at https://serpapi.com (100 searches/month free)."
    )
