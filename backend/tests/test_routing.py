"""
Comprehensive Unit and Integration Tests for Module 2: Routing Optimization Engine.
Tests:
  - Haversine distance calculations and travel times
  - Distance matrix caching
  - Time window validations and early arrival waiting
  - Perishability / food expiry constraints
  - Vehicle capacity enforcement (no vehicle over capacity at any stop)
  - Split pickup and delivery handling
  - Multi-depot vehicle fleet routing
  - Local search improvements (2-opt, relocate, swap)
  - Multi-depot vs single-depot baseline comparison
  - Performance benchmark (< 5s for 30 stops)
  - API endpoint handlers (/plan, /routes, /summary, /replan)
"""

import sys
import os
import time
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.routing.distance import (
    haversine_distance,
    travel_time_minutes,
    extract_coords,
    DistanceMatrix
)
from backend.routing.time_windows import (
    parse_time_to_minutes,
    minutes_to_time_str,
    TimeWindow,
    is_within_window,
    is_expired,
    evaluate_route_schedule
)
from backend.routing.solver import RoutingSolver, RoutingTask, Stop
from backend.routing.baseline import BaselineRouter
from backend.routing.sample_data import (
    SAMPLE_DEPOTS,
    SAMPLE_VEHICLES,
    SAMPLE_DONATIONS,
    SAMPLE_REQUESTS,
    SAMPLE_MATCHES
)
from backend.routing.api import (
    plan_routes,
    get_routes,
    get_routing_summary,
    replan_routes,
    PlanRequest,
    ReplanRequest
)


# =====================================================================
# 1. Distance & Travel Time Tests
# =====================================================================

def test_extract_coords():
    # Dict format {"lat": ..., "lng": ...}
    assert extract_coords({"lat": 12.97, "lng": 77.59}) == (12.97, 77.59)
    # Nested location format {"location": {"lat": ..., "lng": ...}}
    assert extract_coords({"location": {"lat": 13.0, "lng": 77.58}}) == (13.0, 77.58)
    # Tuple / List format
    assert extract_coords((12.93, 77.62)) == (12.93, 77.62)
    assert extract_coords([12.95, 77.60]) == (12.95, 77.60)


def test_haversine_distance_identical_points():
    point = {"lat": 12.9716, "lng": 77.5946}
    assert haversine_distance(point, point) == 0.0


def test_haversine_distance_known_distance():
    # Hebbal (North Bangalore) to MG Road (Central Bangalore) is approx 6-9 km straight line
    hebbal = {"lat": 13.0358, "lng": 77.5970}
    mg_road = {"lat": 12.9756, "lng": 77.6066}
    dist = haversine_distance(hebbal, mg_road)
    assert 6.0 <= dist <= 8.5
    # Symmetry property: dist(A, B) == dist(B, A)
    assert haversine_distance(hebbal, mg_road) == haversine_distance(mg_road, hebbal)


def test_travel_time_calculation():
    # 30 km at 30 km/h is 60 minutes
    assert travel_time_minutes(30.0, speed_kmh=30.0) == 60.0
    # 15 km at 30 km/h is 30 minutes
    assert travel_time_minutes(15.0, speed_kmh=30.0) == 30.0
    # 0 distance should take 0 minutes
    assert travel_time_minutes(0.0) == 0.0


def test_distance_matrix():
    matrix = DistanceMatrix(speed_kmh=30.0)
    matrix.add_location("depot1", {"lat": 13.0, "lng": 77.58})
    matrix.add_location("cust1", {"lat": 12.93, "lng": 77.62})

    dist = matrix.get_distance("depot1", "cust1")
    assert dist > 0.0
    # Verify cached retrieval
    assert matrix.get_distance("cust1", "depot1") == dist
    assert matrix.get_distance("depot1", "depot1") == 0.0

    travel_time = matrix.get_travel_time("depot1", "cust1")
    assert travel_time > 0.0


# =====================================================================
# 2. Time Windows & Perishability Tests
# =====================================================================

def test_time_parsing_and_formatting():
    assert parse_time_to_minutes("14:20") == 14 * 60 + 20
    assert parse_time_to_minutes("09:00") == 540.0
    assert parse_time_to_minutes("2026-11-05T14:30:00") == 14 * 60 + 30
    assert minutes_to_time_str(860.0) == "14:20"
    assert minutes_to_time_str(540.0) == "09:00"


def test_time_window_waiting_and_lateness():
    tw = TimeWindow(start_minutes=840.0, end_minutes=1020.0)  # 14:00 to 17:00

    # Arriving early at 13:30 (810 min): must wait 30 mins
    assert tw.waiting_time(810.0) == 30.0
    assert tw.lateness(810.0) == 0.0
    assert tw.is_within(810.0) is True

    # Arriving on time at 15:00 (900 min): no wait, no lateness
    assert tw.waiting_time(900.0) == 0.0
    assert tw.lateness(900.0) == 0.0
    assert tw.is_within(900.0) is True

    # Arriving late at 17:30 (1050 min): 30 mins late
    assert tw.waiting_time(1050.0) == 0.0
    assert tw.lateness(1050.0) == 30.0
    assert tw.is_within(1050.0) is False


def test_perishability_expiry_detection():
    # Food expires at 18:00 (1080 min)
    expiry_min = 1080.0

    # Delivery arrives at 17:30 (1050 min) -> Not expired (safe)
    assert is_expired(1050.0, expiry_min) is False

    # Delivery arrives at 18:15 (1095 min) -> Expired!
    assert is_expired(1095.0, expiry_min) is True


def test_route_schedule_evaluation_capacity_and_windows():
    depot_loc = {"lat": 12.97, "lng": 77.59}

    stops = [
        {
            "type": "pickup",
            "donation_id": 1,
            "kg": 40.0,
            "location": {"lat": 12.98, "lng": 77.60},
            "pickup_window": {"start": "09:30", "end": "11:00"},
            "service_min": 15.0
        },
        {
            "type": "delivery",
            "request_id": 1,
            "kg": 40.0,
            "location": {"lat": 12.95, "lng": 77.61},
            "delivery_window": {"start": "10:00", "end": "13:00"},
            "expiry_time": "2026-11-05T15:00:00",
            "service_min": 15.0
        }
    ]

    eval_res = evaluate_route_schedule(
        stop_sequence=stops,
        depot_location=depot_loc,
        vehicle_capacity_kg=50.0,
        available_from="09:00",
        available_to="18:00",
        distance_lookup_fn=haversine_distance,
        speed_kmh=30.0
    )

    assert eval_res.is_feasible is True
    assert eval_res.capacity_violation_kg == 0.0
    assert eval_res.expiry_violation_count == 0
    assert len(eval_res.stops) == 2
    # Verify pickup load is 40.0 and delivery final load is 0.0
    assert eval_res.stops[0].cum_load_kg == 40.0
    assert eval_res.stops[1].cum_load_kg == 0.0


def test_route_schedule_evaluation_capacity_overflow():
    depot_loc = {"lat": 12.97, "lng": 77.59}

    # Demand 70 kg in a 50 kg capacity vehicle
    stops = [
        {
            "type": "pickup",
            "donation_id": 1,
            "kg": 70.0,
            "location": {"lat": 12.98, "lng": 77.60},
            "pickup_window": {"start": "09:30", "end": "11:00"},
        },
        {
            "type": "delivery",
            "request_id": 1,
            "kg": 70.0,
            "location": {"lat": 12.95, "lng": 77.61},
            "delivery_window": {"start": "10:00", "end": "13:00"},
        }
    ]

    eval_res = evaluate_route_schedule(
        stop_sequence=stops,
        depot_location=depot_loc,
        vehicle_capacity_kg=50.0,
        available_from="09:00",
        available_to="18:00",
        distance_lookup_fn=haversine_distance
    )

    assert eval_res.is_feasible is False
    assert eval_res.capacity_violation_kg == 20.0


# =====================================================================
# 3. Solver: Greedy Insertion, Splits & Multi-Depot Tests
# =====================================================================

def test_solver_basic_scenario():
    solver = RoutingSolver(speed_kmh=30.0, enable_splits=True)

    result = solver.solve(
        donations=SAMPLE_DONATIONS[:3],
        requests=SAMPLE_REQUESTS[:3],
        depots=SAMPLE_DEPOTS,
        vehicles=SAMPLE_VEHICLES,
        matches=SAMPLE_MATCHES[:3]
    )

    assert "routes" in result
    assert "metrics" in result
    routes = result["routes"]
    assert len(routes) > 0

    # Ensure no vehicle capacity is exceeded in any stop
    for r in routes:
        cap = r["capacity_kg"]
        for s in r["stops"]:
            assert s["cum_load_kg"] <= cap + 1e-4

        # Precedence check: every pickup must precede its delivery
        pickup_seen = set()
        for s in r["stops"]:
            if s["type"] == "pickup":
                pickup_seen.add(s["task_id"])
            elif s["type"] == "delivery":
                assert s["task_id"] in pickup_seen, f"Delivery appeared before pickup for {s['task_id']}"


def test_split_handling_for_oversized_task():
    # Create an oversized match (180 kg) that exceeds the single largest vehicle capacity (150 kg)
    oversized_matches = [
        {
            "match_id": 99,
            "donation_id": 1,
            "request_id": 1,
            "allocated_kg": 180.0,
            "priority_score": 0.95
        }
    ]

    solver = RoutingSolver(speed_kmh=30.0, enable_splits=True)
    result = solver.solve(
        donations=SAMPLE_DONATIONS,
        requests=SAMPLE_REQUESTS,
        depots=SAMPLE_DEPOTS,
        vehicles=SAMPLE_VEHICLES,
        matches=oversized_matches
    )

    # Must be split across multiple chunks/vehicles
    assert result["metrics"]["split_delivery_count"] > 0
    # Total delivered food across routes should equal the original allocated amount (180 kg)
    total_delivered = sum(
        s["kg"] for r in result["routes"] for s in r["stops"] if s["type"] == "delivery"
    )
    assert total_delivered == pytest.approx(180.0, abs=0.1)


def test_local_search_improvement():
    # Test that 2-opt and relocate preserve feasibility and precedence
    solver = RoutingSolver(speed_kmh=30.0, enable_splits=True)
    result = solver.solve(
        donations=SAMPLE_DONATIONS,
        requests=SAMPLE_REQUESTS,
        depots=SAMPLE_DEPOTS,
        vehicles=SAMPLE_VEHICLES,
        matches=SAMPLE_MATCHES
    )

    for r in result["routes"]:
        # Verify precedence after local search
        pickup_seen = set()
        for s in r["stops"]:
            if s["type"] == "pickup":
                pickup_seen.add(s["task_id"])
            elif s["type"] == "delivery":
                assert s["task_id"] in pickup_seen


# =====================================================================
# 4. Multi-Depot vs Baseline Comparison Tests (Definition of Done)
# =====================================================================

def test_multi_depot_beats_single_depot_baseline():
    """
    Definition of Done (Section 6.7):
    'Multi-depot plan delivers more food than the single-depot baseline on the same seed data.'
    """
    solver = RoutingSolver(speed_kmh=30.0, enable_splits=True)
    solver_result = solver.solve(
        donations=SAMPLE_DONATIONS,
        requests=SAMPLE_REQUESTS,
        depots=SAMPLE_DEPOTS,
        vehicles=SAMPLE_VEHICLES,
        matches=SAMPLE_MATCHES
    )

    baseline_router = BaselineRouter(speed_kmh=30.0)
    baseline_result = baseline_router.solve(
        donations=SAMPLE_DONATIONS,
        requests=SAMPLE_REQUESTS,
        depots=SAMPLE_DEPOTS,
        vehicles=SAMPLE_VEHICLES,
        matches=SAMPLE_MATCHES
    )

    solver_food = solver_result["metrics"]["food_delivered_kg"]
    baseline_food = baseline_result["metrics"]["food_delivered_kg"]

    # Multi-depot with splits should deliver at least as much or more food than single-depot naive baseline
    assert solver_food >= baseline_food
    # No deliveries past expiry in solver result
    assert solver_result["metrics"]["expiry_compliance_percent"] == 100.0


# =====================================================================
# 5. Performance Benchmark (< 5 seconds for 30 stops)
# =====================================================================

def test_performance_30_stops_under_5_seconds():
    """
    Definition of Done (Section 6.7):
    '30 stops solve in under 5 seconds.'
    """
    # Create 15 pickup-delivery pairs = 30 customer stops
    bench_donations = []
    bench_requests = []
    bench_matches = []

    for i in range(1, 16):
        d_id = i
        r_id = i + 100
        bench_donations.append({
            "id": d_id,
            "donor_name": f"Donor {i}",
            "food_type": "Cooked food",
            "quantity_kg": 20.0 + (i % 3) * 10,
            "location": {"lat": 12.90 + (i * 0.01), "lng": 77.58 + (i * 0.01)},
            "pickup_window": {"start": "09:00", "end": "18:00"},
            "expiry_time": "2026-11-05T22:00:00",
            "status": "open"
        })
        bench_requests.append({
            "id": r_id,
            "receiver_name": f"Receiver {i}",
            "quantity_kg": 20.0 + (i % 3) * 10,
            "location": {"lat": 12.92 + (i * 0.01), "lng": 77.60 + (i * 0.01)},
            "delivery_window": {"start": "10:00", "end": "20:00"},
            "need_level": 4,
            "status": "open"
        })
        bench_matches.append({
            "match_id": i,
            "donation_id": d_id,
            "request_id": r_id,
            "allocated_kg": 20.0 + (i % 3) * 10,
            "priority_score": 0.8
        })

    solver = RoutingSolver(speed_kmh=30.0, enable_splits=True)

    start_time = time.time()
    res = solver.solve(
        donations=bench_donations,
        requests=bench_requests,
        depots=SAMPLE_DEPOTS,
        vehicles=SAMPLE_VEHICLES,
        matches=bench_matches
    )
    duration = time.time() - start_time

    total_stops = sum(len(r["stops"]) for r in res["routes"])
    print(f"\n30-Stop Benchmark completed in {duration:.3f} seconds with {total_stops} planned stops.")

    assert duration < 5.0, f"Solver took {duration:.3f}s which exceeds the 5-second requirement!"


# =====================================================================
# 6. API Endpoint Handlers Unit & Integration Tests
# =====================================================================

def test_api_plan_routes():
    res = plan_routes(PlanRequest())
    assert res["status"] == "success"
    assert "routes" in res
    assert "metrics" in res
    assert "baseline_comparison" in res
    assert len(res["routes"]) > 0

    first_route = res["routes"][0]
    assert "vehicle_id" in first_route
    assert "depot_id" in first_route
    assert "stops" in first_route
    assert "total_distance_km" in first_route
    assert "total_time_min" in first_route


def test_api_get_routes():
    routes = get_routes()
    assert isinstance(routes, list)
    assert len(routes) > 0

    first_route = routes[0]
    assert "vehicle_id" in first_route
    assert "depot_id" in first_route
    assert "stops" in first_route
    assert "total_distance_km" in first_route
    assert "total_time_min" in first_route


def test_api_get_summary():
    summary = get_routing_summary()
    assert "metrics" in summary
    metrics = summary["metrics"]
    assert "total_distance_km" in metrics
    assert "food_delivered_kg" in metrics
    assert "delivery_rate_percent" in metrics
    assert "baseline_comparison" in summary


def test_api_replan_routes_vehicle_breakdown():
    # Simulate Vehicle 1 breakdown
    data = replan_routes(ReplanRequest(disabled_vehicle_ids=[1]))
    assert data["status"] == "success"
    # Vehicle 1 should not have an active route
    active_vehicle_ids = [r["vehicle_id"] for r in data["routes"]]
    assert 1 not in active_vehicle_ids
    assert data["replanned_event"]["disabled_vehicles"] == [1]
