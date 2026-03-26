from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BusinessResult:
    place_id: Optional[str] = None
    business_name: str = ""
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    raw_data: Optional[dict] = field(default_factory=dict)


class BaseMapsProvider(ABC):
    @abstractmethod
    def search(self, query: str, location: str, max_results: int = 60) -> list[BusinessResult]:
        """Search for businesses and return a list of BusinessResult."""
        ...

    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and tracking."""
        ...
