"""
Distance and travel time calculation utilities for FoodRoute.
Uses the Haversine formula for spherical distance and configurable urban speeds.
"""

import math
from typing import Dict, Any, Tuple, Union, List, Optional

# Standard mean radius of Earth in kilometers
EARTH_RADIUS_KM = 6371.0

# Default urban commercial vehicle travel speed in km/h
DEFAULT_SPEED_KMH = 30.0

# Default service time per stop (loading / unloading) in minutes
DEFAULT_SERVICE_TIME_MIN = 15.0


def extract_coords(point: Union[Dict[str, Any], Tuple[float, float], List[float], Any]) -> Tuple[float, float]:
    """
    Extracts (latitude, longitude) as floats from various representation formats.
    Supports:
      - dict: {"lat": 12.97, "lng": 77.59} or {"latitude": 12.97, "longitude": 77.59}
      - tuple or list: (12.97, 77.59)
      - object with .lat and .lng or .latitude and .longitude attributes
    """
    if isinstance(point, (tuple, list)):
        if len(point) < 2:
            raise ValueError(f"Invalid coordinate sequence: {point}")
        return float(point[0]), float(point[1])

    if isinstance(point, dict):
        if "location" in point and isinstance(point["location"], dict):
            point = point["location"]

        if "lat" in point and "lng" in point:
            return float(point["lat"]), float(point["lng"])
        if "lat" in point and "lon" in point:
            return float(point["lat"]), float(point["lon"])
        if "latitude" in point and "longitude" in point:
            return float(point["latitude"]), float(point["longitude"])
        raise ValueError(f"Could not extract lat/lng from dictionary: {point}")

    if hasattr(point, "lat") and hasattr(point, "lng"):
        return float(point.lat), float(point.lng)
    if hasattr(point, "latitude") and hasattr(point, "longitude"):
        return float(point.latitude), float(point.longitude)

    raise TypeError(f"Unsupported coordinate type: {type(point)}")


def haversine_distance(
    point1: Union[Dict[str, Any], Tuple[float, float], List[float], Any],
    point2: Union[Dict[str, Any], Tuple[float, float], List[float], Any]
) -> float:
    """
    Computes great-circle distance between two geographic coordinates in kilometers
    using the Haversine formula.

    Returns:
        float: Distance in kilometers rounded to 3 decimal places.
    """
    lat1, lng1 = extract_coords(point1)
    lat2, lng2 = extract_coords(point2)

    # Identical coordinates check
    if math.isclose(lat1, lat2, abs_tol=1e-7) and math.isclose(lng1, lng2, abs_tol=1e-7):
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    
    # Numerical safeguard against precision loss
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = EARTH_RADIUS_KM * c
    return round(distance, 3)


def travel_time_minutes(distance_km: float, speed_kmh: float = DEFAULT_SPEED_KMH) -> float:
    """
    Calculates estimated travel time in minutes based on distance and average speed.

    Args:
        distance_km: Distance in kilometers.
        speed_kmh: Vehicle average speed in km/h (default: 30 km/h).

    Returns:
        float: Travel time in minutes rounded to 2 decimal places.
    """
    if speed_kmh <= 0:
        raise ValueError(f"Vehicle speed must be strictly positive, got {speed_kmh}")
    if distance_km <= 0:
        return 0.0

    minutes = (distance_km / speed_kmh) * 60.0
    return round(minutes, 2)


class DistanceMatrix:
    """
    Fast distance and travel time lookup matrix between any set of locations.
    Can be initialized with a dictionary of locations {location_id: (lat, lng)}
    or populated lazily.
    """

    def __init__(self, locations: Optional[Dict[str, Any]] = None, speed_kmh: float = DEFAULT_SPEED_KMH):
        self.speed_kmh = speed_kmh
        self.locations: Dict[str, Tuple[float, float]] = {}
        self._distance_cache: Dict[Tuple[str, str], float] = {}
        self._time_cache: Dict[Tuple[str, str], float] = {}

        if locations:
            for loc_id, loc_data in locations.items():
                self.add_location(str(loc_id), loc_data)

    def add_location(self, loc_id: str, location: Any) -> None:
        """Register a location key with its coordinates."""
        self.locations[str(loc_id)] = extract_coords(location)

    def get_distance(self, from_id: Any, to_id: Any) -> float:
        """
        Get distance in km between two registered location IDs.
        Uses symmetric memoization.
        """
        f_id, t_id = str(from_id), str(to_id)
        if f_id == t_id:
            return 0.0

        pair = (f_id, t_id)
        if pair in self._distance_cache:
            return self._distance_cache[pair]

        reverse_pair = (t_id, f_id)
        if reverse_pair in self._distance_cache:
            dist = self._distance_cache[reverse_pair]
            self._distance_cache[pair] = dist
            return dist

        if f_id not in self.locations:
            raise KeyError(f"Location ID '{f_id}' not found in DistanceMatrix")
        if t_id not in self.locations:
            raise KeyError(f"Location ID '{t_id}' not found in DistanceMatrix")

        dist = haversine_distance(self.locations[f_id], self.locations[t_id])
        self._distance_cache[pair] = dist
        self._distance_cache[reverse_pair] = dist
        return dist

    def get_travel_time(self, from_id: Any, to_id: Any, speed_kmh: Optional[float] = None) -> float:
        """Get travel time in minutes between two registered location IDs."""
        speed = speed_kmh or self.speed_kmh
        f_id, t_id = str(from_id), str(to_id)
        
        pair = (f_id, t_id)
        if speed == self.speed_kmh and pair in self._time_cache:
            return self._time_cache[pair]

        dist = self.get_distance(f_id, t_id)
        time_min = travel_time_minutes(dist, speed)
        
        if speed == self.speed_kmh:
            self._time_cache[pair] = time_min
            self._time_cache[(t_id, f_id)] = time_min

        return time_min

