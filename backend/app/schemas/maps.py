from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

# ─── Australian Presets ──────────────────────────────────────────────────────

AUSTRALIAN_CITIES = [
    {"city": "Sydney", "state": "NSW"},
    {"city": "Melbourne", "state": "VIC"},
    {"city": "Brisbane", "state": "QLD"},
    {"city": "Perth", "state": "WA"},
    {"city": "Adelaide", "state": "SA"},
    {"city": "Gold Coast", "state": "QLD"},
    {"city": "Canberra", "state": "ACT"},
    {"city": "Hobart", "state": "TAS"},
    {"city": "Darwin", "state": "NT"},
    {"city": "Newcastle", "state": "NSW"},
    {"city": "Wollongong", "state": "NSW"},
    {"city": "Geelong", "state": "VIC"},
    {"city": "Cairns", "state": "QLD"},
    {"city": "Townsville", "state": "QLD"},
    {"city": "Toowoomba", "state": "QLD"},
]

BUSINESS_CATEGORIES = [
    "Dentist", "Plumber", "Electrician", "Lawyer", "Accountant",
    "Real Estate Agent", "Restaurant", "Cafe", "Gym", "Physiotherapist",
    "Chiropractor", "Mechanic", "Hair Salon", "Beauty Salon", "Vet",
    "Doctor", "Pharmacy", "Florist", "Pet Shop", "Bakery",
    "Builder", "Painter", "Landscaper", "Cleaner", "Photographer",
]


# ─── Request Schemas ─────────────────────────────────────────────────────────

class MapSearchCreate(BaseModel):
    query_text: Optional[str] = None
    category: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    max_results: int = 60

    @field_validator("max_results")
    @classmethod
    def validate_max_results(cls, v):
        if v < 1 or v > 200:
            raise ValueError("max_results must be between 1 and 200")
        return v

    def effective_query(self) -> str:
        if self.query_text:
            return self.query_text
        parts = []
        if self.category:
            parts.append(self.category)
        if self.city:
            parts.append(f"in {self.city}")
        if self.state:
            parts.append(self.state)
        return " ".join(parts) if parts else ""

    def effective_location(self) -> str:
        if self.city and self.state:
            return f"{self.city}, {self.state}, Australia"
        if self.city:
            return f"{self.city}, Australia"
        return "Australia"


# ─── Response Schemas ────────────────────────────────────────────────────────

class BusinessListingPublic(BaseModel):
    id: int
    search_query_id: int
    place_id: Optional[str] = None
    business_name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    category: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class BusinessListingList(BaseModel):
    items: list[BusinessListingPublic]
    total: int
    page: int
    per_page: int


class MapSearchPublic(BaseModel):
    id: int
    query_text: str
    category: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    status: str
    results_count: int
    provider: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class MapSearchList(BaseModel):
    items: list[MapSearchPublic]
    total: int
    page: int
    per_page: int
