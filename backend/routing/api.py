"""
FastAPI Endpoints for Module 2: Routing Optimization Engine.
Provides:
  - POST /routing/plan
  - GET  /routing/routes
  - GET  /routing/summary
  - POST /routing/replan
"""

import copy
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .solver import RoutingSolver
from .baseline import BaselineRouter
from .sample_data import (
    SAMPLE_DEPOTS,
    SAMPLE_VEHICLES,
    SAMPLE_DONATIONS,
    SAMPLE_REQUESTS,
    SAMPLE_MATCHES
)

router = APIRouter(prefix="/routing", tags=["Routing Engine (Module 2)"])


# In-memory storage for the latest routing solution and baseline metrics
_routing_state: Dict[str, Any] = {
    "latest_solution": None,
    "latest_baseline": None,
    "current_donations": SAMPLE_DONATIONS,
    "current_requests": SAMPLE_REQUESTS,
    "current_depots": SAMPLE_DEPOTS,
    "current_vehicles": SAMPLE_VEHICLES,
    "current_matches": SAMPLE_MATCHES
}


class PlanRequest(BaseModel):
    donations: Optional[List[Dict[str, Any]]] = Field(default=None, description="List of donations")
    requests: Optional[List[Dict[str, Any]]] = Field(default=None, description="List of requests")
    depots: Optional[List[Dict[str, Any]]] = Field(default=None, description="List of depots")
    vehicles: Optional[List[Dict[str, Any]]] = Field(default=None, description="List of fleet vehicles")
    matches: Optional[List[Dict[str, Any]]] = Field(default=None, description="List of matches from Module 1")
    speed_kmh: Optional[float] = Field(default=30.0, description="Average vehicle travel speed in km/h")
    service_time_min: Optional[float] = Field(default=15.0, description="Stop service time in minutes")
    enable_splits: Optional[bool] = Field(default=True, description="Enable split deliveries")
    compare_baseline: Optional[bool] = Field(default=True, description="Compute comparison with single-depot baseline")


class ReplanRequest(BaseModel):
    disabled_vehicle_ids: Optional[List[int]] = Field(default_factory=list, description="IDs of vehicles out of service")
    new_donations: Optional[List[Dict[str, Any]]] = Field(default=None, description="Additional donations")
    new_requests: Optional[List[Dict[str, Any]]] = Field(default=None, description="Additional requests")
    new_matches: Optional[List[Dict[str, Any]]] = Field(default=None, description="Additional matches")
    speed_kmh: Optional[float] = Field(default=30.0, description="Average speed in km/h")


def _run_optimization(
    donations: List[Dict[str, Any]],
    requests: List[Dict[str, Any]],
    depots: List[Dict[str, Any]],
    vehicles: List[Dict[str, Any]],
    matches: List[Dict[str, Any]],
    speed_kmh: float = 30.0,
    service_time_min: float = 15.0,
    enable_splits: bool = True,
    compare_baseline: bool = True
) -> Dict[str, Any]:
    """Helper to run the solver and baseline comparator."""
    solver = RoutingSolver(
        speed_kmh=speed_kmh,
        service_time_min=service_time_min,
        enable_splits=enable_splits
    )

    solution = solver.solve(
        donations=donations,
        requests=requests,
        depots=depots,
        vehicles=vehicles,
        matches=matches
    )

    baseline_data = None
    if compare_baseline:
        baseline_solver = BaselineRouter(
            speed_kmh=speed_kmh,
            service_time_min=service_time_min
        )
        baseline_res = baseline_solver.solve(
            donations=donations,
            requests=requests,
            depots=depots,
            vehicles=vehicles,
            matches=matches
        )

        b_dist = baseline_res["metrics"]["total_distance_km"]
        b_del = baseline_res["metrics"]["food_delivered_kg"]
        s_dist = solution["metrics"]["total_distance_km"]
        s_del = solution["metrics"]["food_delivered_kg"]

        dist_saved = round(max(0.0, b_dist - s_dist), 2)
        dist_saved_pct = round((dist_saved / b_dist * 100.0), 1) if b_dist > 0 else 0.0

        extra_food = round(max(0.0, s_del - b_del), 2)
        extra_food_pct = round((extra_food / b_del * 100.0), 1) if b_del > 0 else 0.0

        baseline_data = {
            "baseline_distance_km": b_dist,
            "baseline_food_delivered_kg": b_del,
            "distance_reduction_km": dist_saved,
            "distance_reduction_percent": dist_saved_pct,
            "additional_food_delivered_kg": extra_food,
            "food_delivery_gain_percent": extra_food_pct,
            "multi_depot_advantage_notes": (
                f"Multi-depot routing with splits delivered {extra_food} kg more surplus food "
                f"(+{extra_food_pct}%) while cutting fleet travel distance by {dist_saved} km (-{dist_saved_pct}%)."
            ),
            "baseline_metrics": baseline_res["metrics"]
        }

    # Store state
    _routing_state["latest_solution"] = solution
    _routing_state["latest_baseline"] = baseline_data
    _routing_state["current_donations"] = donations
    _routing_state["current_requests"] = requests
    _routing_state["current_depots"] = depots
    _routing_state["current_vehicles"] = vehicles
    _routing_state["current_matches"] = matches

    return {
        "status": "success",
        "routes": solution["routes"],
        "unserved_tasks": solution["unserved_tasks"],
        "metrics": solution["metrics"],
        "baseline_comparison": baseline_data
    }


@router.post("/plan")
def plan_routes(request: Optional[PlanRequest] = None):
    """
    Builds optimized multi-depot, split-delivery vehicle routes from matches.
    If no input is provided, executes using benchmark seed data.
    """
    donations = (request.donations if request and request.donations is not None else _routing_state["current_donations"])
    requests_list = (request.requests if request and request.requests is not None else _routing_state["current_requests"])
    depots = (request.depots if request and request.depots is not None else _routing_state["current_depots"])
    vehicles = (request.vehicles if request and request.vehicles is not None else _routing_state["current_vehicles"])
    matches = (request.matches if request and request.matches is not None else _routing_state["current_matches"])

    speed = request.speed_kmh if request and request.speed_kmh else 30.0
    service_time = request.service_time_min if request and request.service_time_min else 15.0
    splits = request.enable_splits if request and request.enable_splits is not None else True
    compare = request.compare_baseline if request and request.compare_baseline is not None else True

    result = _run_optimization(
        donations=donations,
        requests=requests_list,
        depots=depots,
        vehicles=vehicles,
        matches=matches,
        speed_kmh=speed,
        service_time_min=service_time,
        enable_splits=splits,
        compare_baseline=compare
    )
    return result


@router.get("/routes")
def get_routes():
    """
    Retrieves the latest planned vehicle routes matching the Section 4.1 contract.
    If no plan has been computed yet, automatically generates one using default seed data.
    """
    if _routing_state["latest_solution"] is None:
        _run_optimization(
            donations=_routing_state["current_donations"],
            requests=_routing_state["current_requests"],
            depots=_routing_state["current_depots"],
            vehicles=_routing_state["current_vehicles"],
            matches=_routing_state["current_matches"]
        )

    solution = _routing_state["latest_solution"]
    return solution.get("routes", [])


@router.get("/summary")
def get_routing_summary():
    """
    Retrieves summary metrics for the routing plan:
    totals for distance, duration, food delivered, unserved tasks, vehicle utilization,
    split deliveries, and baseline comparison.
    """
    if _routing_state["latest_solution"] is None:
        _run_optimization(
            donations=_routing_state["current_donations"],
            requests=_routing_state["current_requests"],
            depots=_routing_state["current_depots"],
            vehicles=_routing_state["current_vehicles"],
            matches=_routing_state["current_matches"]
        )

    solution = _routing_state["latest_solution"]
    baseline = _routing_state["latest_baseline"]

    return {
        "metrics": solution.get("metrics", {}),
        "unserved_count": len(solution.get("unserved_tasks", [])),
        "unserved_tasks": solution.get("unserved_tasks", []),
        "baseline_comparison": baseline
    }


@router.post("/replan")
def replan_routes(request: ReplanRequest):
    """
    Dynamic re-planning endpoint:
    Handles runtime disruptions such as vehicle breakdowns (disabled_vehicle_ids)
    or new urgent donations and matches.
    """
    vehicles = [copy.deepcopy(v) for v in _routing_state["current_vehicles"]]
    
    # Apply vehicle status changes
    disabled_ids = set(request.disabled_vehicle_ids or [])
    for v in vehicles:
        if v["id"] in disabled_ids:
            v["is_active"] = False

    donations = list(_routing_state["current_donations"])
    if request.new_donations:
        donations.extend(request.new_donations)

    requests_list = list(_routing_state["current_requests"])
    if request.new_requests:
        requests_list.extend(request.new_requests)

    matches = list(_routing_state["current_matches"])
    if request.new_matches:
        matches.extend(request.new_matches)

    speed = request.speed_kmh if request.speed_kmh else 30.0

    result = _run_optimization(
        donations=donations,
        requests=requests_list,
        depots=depots if (depots := _routing_state["current_depots"]) else SAMPLE_DEPOTS,
        vehicles=vehicles,
        matches=matches,
        speed_kmh=speed
    )

    result["replanned_event"] = {
        "disabled_vehicles": list(disabled_ids),
        "new_donations_count": len(request.new_donations or []),
        "new_requests_count": len(request.new_requests or []),
        "new_matches_count": len(request.new_matches or []),
        "active_fleet_size": sum(1 for v in vehicles if v.get("is_active", True))
    }
    return result
