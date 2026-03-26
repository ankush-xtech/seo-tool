"""
SerpAPI Google Maps provider.
Uses the SerpAPI Google Maps engine to fetch business listings.
Free tier: 100 searches/month. Paid plans for production use.
"""
import logging
import requests as req_lib
from typing import Optional
from .base_provider import BaseMapsProvider, BusinessResult

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"


class SerpAPIProvider(BaseMapsProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    def name(self) -> str:
        return "serpapi"

    def search(self, query: str, location: str, max_results: int = 60) -> list[BusinessResult]:
        results: list[BusinessResult] = []
        start = 0

        while len(results) < max_results:
            params = {
                "engine": "google_maps",
                "q": query,
                "ll": None,  # Let SerpAPI resolve from location text
                "type": "search",
                "api_key": self.api_key,
                "start": start,
                "num": 20,
            }
            # Use google_maps engine with location text
            # SerpAPI resolves Australian locations well
            if location:
                params["q"] = f"{query} {location}"

            try:
                logger.info(f"SerpAPI request: q='{params['q']}' start={start}")
                resp = req_lib.get(SERPAPI_BASE, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"SerpAPI request failed: {e}")
                break

            local_results = data.get("local_results", [])
            if not local_results:
                logger.info("No more results from SerpAPI")
                break

            for item in local_results:
                if len(results) >= max_results:
                    break
                results.append(self._parse_result(item))

            # Check if there's a next page
            if not data.get("serpapi_pagination", {}).get("next"):
                break
            start += 20

        logger.info(f"SerpAPI returned {len(results)} results for '{query}'")
        return results

    def _parse_result(self, item: dict) -> BusinessResult:
        # Extract address components
        address = item.get("address", "")
        city, state, postcode = self._parse_address(address)

        return BusinessResult(
            place_id=item.get("place_id"),
            business_name=item.get("title", ""),
            address=address,
            city=city,
            state=state,
            postcode=postcode,
            phone=item.get("phone"),
            website=item.get("website"),
            rating=item.get("rating"),
            reviews_count=item.get("reviews"),
            category=item.get("type"),
            latitude=item.get("gps_coordinates", {}).get("latitude"),
            longitude=item.get("gps_coordinates", {}).get("longitude"),
            raw_data=item,
        )

    def _parse_address(self, address: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Try to extract city, state, postcode from Australian address string."""
        if not address:
            return None, None, None

        import re
        # Australian pattern: "... City STATE POSTCODE"
        # e.g., "123 Collins St, Melbourne VIC 3000"
        match = re.search(
            r'([A-Za-z\s]+?)\s+(NSW|VIC|QLD|WA|SA|TAS|ACT|NT)\s+(\d{4})',
            address
        )
        if match:
            return match.group(1).strip(), match.group(2), match.group(3)

        # Try to get city from comma-separated parts
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 2:
            return parts[-2] if len(parts) >= 3 else parts[-1], None, None

        return None, None, None
