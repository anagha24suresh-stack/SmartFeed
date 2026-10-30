"""
Routing Optimization Engine (Module 2)
Multi-depot, split pickup/delivery vehicle routing with time windows and perishability constraints.
"""

from .distance import haversine_distance, travel_time_minutes, DistanceMatrix
from .time_windows import (
    TimeWindow,
    parse_time_to_minutes,
    minutes_to_time_str,
    is_within_window,
    is_expired,
    evaluate_route_schedule,
)
from .solver import RoutingSolver, RoutingTask, VehicleRoute, Stop
from .baseline import BaselineRouter
from .api import router as routing_router

__all__ = [
    "haversine_distance",
    "travel_time_minutes",
    "DistanceMatrix",
    "TimeWindow",
    "parse_time_to_minutes",
    "minutes_to_time_str",
    "is_within_window",
    "is_expired",
    "evaluate_route_schedule",
    "RoutingSolver",
    "RoutingTask",
    "VehicleRoute",
    "Stop",
    "BaselineRouter",
    "routing_router",
]

