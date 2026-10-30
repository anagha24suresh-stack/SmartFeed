"""
Sample benchmark data for FoodRoute routing engine.
Contains 3 multi-depots, 5 fleet vehicles, 10 donations, 10 requests, and matches
geographically situated across urban centers (Bangalore).
"""

from typing import Dict, Any, List

SAMPLE_DEPOTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "North Hub (Hebbal)",
        "location": {"lat": 13.0358, "lng": 77.5970}
    },
    {
        "id": 2,
        "name": "Central Hub (MG Road)",
        "location": {"lat": 12.9756, "lng": 77.6066}
    },
    {
        "id": 3,
        "name": "South Hub (Koramangala)",
        "location": {"lat": 12.9352, "lng": 77.6245}
    }
]

SAMPLE_VEHICLES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "depot_id": 1,
        "capacity_kg": 120.0,
        "available_from": "09:00",
        "available_to": "21:00",
        "is_active": True
    },
    {
        "id": 2,
        "depot_id": 1,
        "capacity_kg": 80.0,
        "available_from": "10:00",
        "available_to": "20:00",
        "is_active": True
    },
    {
        "id": 3,
        "depot_id": 2,
        "capacity_kg": 150.0,
        "available_from": "09:00",
        "available_to": "22:00",
        "is_active": True
    },
    {
        "id": 4,
        "depot_id": 2,
        "capacity_kg": 100.0,
        "available_from": "09:30",
        "available_to": "21:30",
        "is_active": True
    },
    {
        "id": 5,
        "depot_id": 3,
        "capacity_kg": 100.0,
        "available_from": "09:00",
        "available_to": "21:00",
        "is_active": True
    }
]

SAMPLE_DONATIONS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "donor_name": "Green Leaf Restaurant",
        "food_type": "Cooked meals",
        "quantity_kg": 40.0,
        "location": {"lat": 12.9716, "lng": 77.5946},
        "ready_time": "2026-11-05T14:00:00",
        "expiry_time": "2026-11-05T20:00:00",
        "pickup_window": {"start": "14:00", "end": "16:30"},
        "status": "open"
    },
    {
        "id": 2,
        "donor_name": "Royal Palace Banquet",
        "food_type": "Buffet surplus",
        "quantity_kg": 85.0,
        "location": {"lat": 13.0112, "lng": 77.5852},
        "ready_time": "2026-11-05T14:30:00",
        "expiry_time": "2026-11-05T19:30:00",
        "pickup_window": {"start": "14:30", "end": "16:45"},
        "status": "open"
    },
    {
        "id": 3,
        "donor_name": "City Bakers & Cafe",
        "food_type": "Bread and pastries",
        "quantity_kg": 30.0,
        "location": {"lat": 12.9345, "lng": 77.6101},
        "ready_time": "2026-11-05T11:00:00",
        "expiry_time": "2026-11-05T22:00:00",
        "pickup_window": {"start": "11:00", "end": "15:00"},
        "status": "open"
    },
    {
        "id": 4,
        "donor_name": "Spice Route Kitchen",
        "food_type": "Rice & Curry packages",
        "quantity_kg": 60.0,
        "location": {"lat": 12.9812, "lng": 77.6410},
        "ready_time": "2026-11-05T13:30:00",
        "expiry_time": "2026-11-05T18:30:00",
        "pickup_window": {"start": "13:30", "end": "16:00"},
        "status": "open"
    },
    {
        "id": 5,
        "donor_name": "Fresh Harvest Supermarket",
        "food_type": "Fresh produce & fruits",
        "quantity_kg": 110.0,
        "location": {"lat": 13.0421, "lng": 77.5912},
        "ready_time": "2026-11-05T10:00:00",
        "expiry_time": "2026-11-05T23:00:00",
        "pickup_window": {"start": "10:30", "end": "14:00"},
        "status": "open"
    },
    {
        "id": 6,
        "donor_name": "Cornerstone Deli",
        "food_type": "Sandwiches & wraps",
        "quantity_kg": 25.0,
        "location": {"lat": 12.9280, "lng": 77.6290},
        "ready_time": "2026-11-05T14:00:00",
        "expiry_time": "2026-11-05T19:00:00",
        "pickup_window": {"start": "14:00", "end": "16:00"},
        "status": "open"
    },
    {
        "id": 7,
        "donor_name": "Grand Hotel Buffet",
        "food_type": "Hot meals",
        "quantity_kg": 75.0,
        "location": {"lat": 12.9650, "lng": 77.5750},
        "ready_time": "2026-11-05T15:00:00",
        "expiry_time": "2026-11-05T20:00:00",
        "pickup_window": {"start": "15:00", "end": "17:30"},
        "status": "open"
    },
    {
        "id": 8,
        "donor_name": "Corporate Cafeteria Hub",
        "food_type": "Cooked lunch platters",
        "quantity_kg": 90.0,
        "location": {"lat": 12.9905, "lng": 77.6890},
        "ready_time": "2026-11-05T14:15:00",
        "expiry_time": "2026-11-05T19:45:00",
        "pickup_window": {"start": "14:15", "end": "17:00"},
        "status": "open"
    },
    {
        "id": 9,
        "donor_name": "Sunshine Bakery",
        "food_type": "Breads & buns",
        "quantity_kg": 35.0,
        "location": {"lat": 13.0180, "lng": 77.6400},
        "ready_time": "2026-11-05T12:00:00",
        "expiry_time": "2026-11-05T21:00:00",
        "pickup_window": {"start": "12:00", "end": "15:30"},
        "status": "open"
    },
    {
        "id": 10,
        "donor_name": "Organic Greens Grocers",
        "food_type": "Packaged salads & fruits",
        "quantity_kg": 45.0,
        "location": {"lat": 12.9150, "lng": 77.6050},
        "ready_time": "2026-11-05T13:00:00",
        "expiry_time": "2026-11-05T20:30:00",
        "pickup_window": {"start": "13:00", "end": "16:30"},
        "status": "open"
    }
]

SAMPLE_REQUESTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "receiver_name": "Hope Shelter",
        "quantity_kg": 40.0,
        "location": {"lat": 12.9320, "lng": 77.6200},
        "delivery_window": {"start": "15:00", "end": "19:00"},
        "need_level": 5,
        "status": "open"
    },
    {
        "id": 2,
        "receiver_name": "Peace Community Kitchen",
        "quantity_kg": 50.0,
        "location": {"lat": 13.0050, "lng": 77.5700},
        "delivery_window": {"start": "15:30", "end": "18:30"},
        "need_level": 4,
        "status": "open"
    },
    {
        "id": 3,
        "receiver_name": "St. Jude Children Home",
        "quantity_kg": 35.0,
        "location": {"lat": 13.0195, "lng": 77.5920},
        "delivery_window": {"start": "15:00", "end": "18:00"},
        "need_level": 5,
        "status": "open"
    },
    {
        "id": 4,
        "receiver_name": "Elder Care Haven",
        "quantity_kg": 30.0,
        "location": {"lat": 12.9410, "lng": 77.6150},
        "delivery_window": {"start": "12:00", "end": "16:30"},
        "need_level": 4,
        "status": "open"
    },
    {
        "id": 5,
        "receiver_name": "Eastside Youth Center",
        "quantity_kg": 60.0,
        "location": {"lat": 12.9750, "lng": 77.6520},
        "delivery_window": {"start": "14:30", "end": "18:00"},
        "need_level": 3,
        "status": "open"
    },
    {
        "id": 6,
        "receiver_name": "Mercy Food Pantry",
        "quantity_kg": 70.0,
        "location": {"lat": 13.0510, "lng": 77.5990},
        "delivery_window": {"start": "11:30", "end": "15:30"},
        "need_level": 4,
        "status": "open"
    },
    {
        "id": 7,
        "receiver_name": "Downtown Night Mission",
        "quantity_kg": 65.0,
        "location": {"lat": 12.9690, "lng": 77.5810},
        "delivery_window": {"start": "16:00", "end": "19:30"},
        "need_level": 5,
        "status": "open"
    },
    {
        "id": 8,
        "receiver_name": "Tech Corridor Relief",
        "quantity_kg": 80.0,
        "location": {"lat": 12.9850, "lng": 77.7010},
        "delivery_window": {"start": "15:00", "end": "19:00"},
        "need_level": 3,
        "status": "open"
    },
    {
        "id": 9,
        "receiver_name": "Shanti Ashram",
        "quantity_kg": 40.0,
        "location": {"lat": 13.0250, "lng": 77.6510},
        "delivery_window": {"start": "13:00", "end": "17:00"},
        "need_level": 4,
        "status": "open"
    },
    {
        "id": 10,
        "receiver_name": "South Urban Food Bank",
        "quantity_kg": 45.0,
        "location": {"lat": 12.9100, "lng": 77.5950},
        "delivery_window": {"start": "14:00", "end": "18:00"},
        "need_level": 4,
        "status": "open"
    }
]

SAMPLE_MATCHES: List[Dict[str, Any]] = [
    {
        "match_id": 1,
        "donation_id": 1,
        "request_id": 1,
        "allocated_kg": 40.0,
        "priority_score": 0.92
    },
    {
        "match_id": 2,
        "donation_id": 2,
        "request_id": 2,
        "allocated_kg": 50.0,
        "priority_score": 0.88
    },
    {
        "match_id": 3,
        "donation_id": 2,
        "request_id": 3,
        "allocated_kg": 35.0,
        "priority_score": 0.85
    },
    {
        "match_id": 4,
        "donation_id": 3,
        "request_id": 4,
        "allocated_kg": 30.0,
        "priority_score": 0.78
    },
    {
        "match_id": 5,
        "donation_id": 4,
        "request_id": 5,
        "allocated_kg": 60.0,
        "priority_score": 0.82
    },
    {
        "match_id": 6,
        "donation_id": 5,
        "request_id": 6,
        "allocated_kg": 70.0,
        "priority_score": 0.80
    },
    {
        "match_id": 7,
        "donation_id": 7,
        "request_id": 7,
        "allocated_kg": 65.0,
        "priority_score": 0.89
    },
    {
        "match_id": 8,
        "donation_id": 8,
        "request_id": 8,
        "allocated_kg": 80.0,
        "priority_score": 0.75
    },
    {
        "match_id": 9,
        "donation_id": 9,
        "request_id": 9,
        "allocated_kg": 35.0,
        "priority_score": 0.76
    },
    {
        "match_id": 10,
        "donation_id": 10,
        "request_id": 10,
        "allocated_kg": 45.0,
        "priority_score": 0.84
    }
]

