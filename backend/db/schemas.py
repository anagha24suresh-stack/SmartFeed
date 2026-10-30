from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# Common Sub-Models
class Location(BaseModel):
    lat: float
    lng: float

class TimeWindow(BaseModel):
    start: str
    end: str

# User & Auth Schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: str = Field(default="donor", description="User role: donor, receiver, or admin")

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Depot Schemas
class DepotCreate(BaseModel):
    name: str
    location: Location

class DepotUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[Location] = None

class DepotResponse(BaseModel):
    id: int
    name: str
    location: Location

    model_config = ConfigDict(from_attributes=True)

# Vehicle Schemas
class VehicleCreate(BaseModel):
    depot_id: int
    capacity_kg: float
    available_from: str = "09:00"
    available_to: str = "21:00"
    is_active: bool = True

class VehicleUpdate(BaseModel):
    depot_id: Optional[int] = None
    capacity_kg: Optional[float] = None
    available_from: Optional[str] = None
    available_to: Optional[str] = None
    is_active: Optional[bool] = None

class VehicleResponse(BaseModel):
    id: int
    depot_id: int
    capacity_kg: float
    available_from: str
    available_to: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

# Donation Schemas
class DonationCreate(BaseModel):
    donor_name: str
    food_type: str
    quantity_kg: float
    location: Location
    ready_time: datetime
    expiry_time: datetime
    pickup_window: TimeWindow
    donor_id: Optional[int] = None

class DonationUpdate(BaseModel):
    donor_name: Optional[str] = None
    food_type: Optional[str] = None
    quantity_kg: Optional[float] = None
    remaining_kg: Optional[float] = None
    location: Optional[Location] = None
    ready_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None
    pickup_window: Optional[TimeWindow] = None
    status: Optional[str] = None

class DonationResponse(BaseModel):
    id: int
    donor_name: str
    food_type: str
    quantity_kg: float
    remaining_kg: float
    location: Location
    ready_time: datetime
    expiry_time: datetime
    pickup_window: TimeWindow
    status: str

    model_config = ConfigDict(from_attributes=True)

# Request Schemas
class RequestCreate(BaseModel):
    receiver_name: str
    quantity_kg: float
    location: Location
    delivery_window: TimeWindow
    need_level: int = Field(ge=1, le=5, description="Priority urgency level 1 to 5")
    receiver_id: Optional[int] = None

class RequestUpdate(BaseModel):
    receiver_name: Optional[str] = None
    quantity_kg: Optional[float] = None
    remaining_kg: Optional[float] = None
    location: Optional[Location] = None
    delivery_window: Optional[TimeWindow] = None
    need_level: Optional[int] = Field(None, ge=1, le=5)
    status: Optional[str] = None

class RequestResponse(BaseModel):
    id: int
    receiver_name: str
    quantity_kg: float
    remaining_kg: float
    location: Location
    delivery_window: TimeWindow
    need_level: int
    status: str

    model_config = ConfigDict(from_attributes=True)

# Urgency Score Schemas
class DonationUrgencyScore(BaseModel):
    id: int
    donor_name: str
    food_type: str
    quantity_kg: float
    time_left_hours: float
    expiry_pressure: float
    quantity_weight: float
    pickup_window_tightness: float
    urgency_score: float

class RequestUrgencyScore(BaseModel):
    id: int
    receiver_name: str
    quantity_kg: float
    need_level: int
    need_level_norm: float
    window_tightness: float
    waiting_time_norm: float
    urgency_score: float

class ScoresResponse(BaseModel):
    timestamp: datetime
    donations: List[DonationUrgencyScore]
    requests: List[RequestUrgencyScore]

# Matching Schemas
class MatchItem(BaseModel):
    match_id: int
    donation_id: int
    request_id: int
    donor_name: Optional[str] = None
    receiver_name: Optional[str] = None
    food_type: Optional[str] = None
    allocated_kg: float
    priority_score: float

class UnmatchedItem(BaseModel):
    item_type: str  # "donation" or "request"
    item_id: int
    item_name: str
    unallocated_kg: float
    reason: str

class MatchingResultResponse(BaseModel):
    batch_id: str
    executed_at: datetime
    execution_time_ms: float
    total_donations_evaluated: int
    total_requests_evaluated: int
    total_allocated_kg: float
    matches_count: int
    unmatched_count: int
    matches: List[MatchItem]
    unmatched: List[UnmatchedItem]
