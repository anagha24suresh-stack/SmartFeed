"""
Baseline Routing Engine for FoodRoute.
Implements a naive single-depot, nearest-neighbor router without order splitting.
Used as an empirical baseline to measure the performance advantage of the multi-depot,
split-capable solver (Section 6.6 & 6.7).
"""

from typing import Dict, Any, List, Optional
import time

from .distance import haversine_distance, travel_time_minutes, DEFAULT_SPEED_KMH, DEFAULT_SERVICE_TIME_MIN
from .time_windows import parse_time_to_minutes, evaluate_route_schedule


class BaselineRouter:
    """
    Naive baseline solver:
    - Single-depot: forces all vehicles to start and end at Depot 1.
    - No split deliveries: rejects or skips orders that do not fit in remaining capacity.
    - Nearest-neighbor construction heuristic without local search.
    """

    def __init__(self, speed_kmh: float = DEFAULT_SPEED_KMH, service_time_min: float = DEFAULT_SERVICE_TIME_MIN):
        self.speed_kmh = speed_kmh
        self.service_time_min = service_time_min

    def solve(
        self,
        donations: List[Dict[str, Any]],
        requests: List[Dict[str, Any]],
        depots: List[Dict[str, Any]],
        vehicles: List[Dict[str, Any]],
        matches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        start_time = time.time()

        if not depots or not vehicles or not matches:
            return {
                "routes": [],
                "unserved_tasks": [],
                "metrics": {
                    "total_distance_km": 0.0,
                    "total_time_min": 0.0,
                    "food_delivered_kg": 0.0,
                    "delivery_rate_percent": 0.0,
                    "unserved_count": 0,
                }
            }

        # Single Depot restriction: pick the first depot
        primary_depot = depots[0]
        depot_loc = primary_depot["location"]

        donations_map = {d["id"]: d for d in donations}
        requests_map = {r["id"]: r for r in requests}

        # Prepare tasks without splits
        tasks = []
        for m in matches:
            d = donations_map.get(m["donation_id"])
            r = requests_map.get(m["request_id"])
            if d and r:
                tasks.append({
                    "match_id": m.get("match_id", m.get("id")),
                    "donation_id": m["donation_id"],
                    "request_id": m["request_id"],
                    "donor_name": d.get("donor_name", ""),
                    "receiver_name": r.get("receiver_name", ""),
                    "quantity_kg": float(m.get("allocated_kg", 0.0)),
                    "pickup_location": d["location"],
                    "pickup_window": d.get("pickup_window"),
                    "delivery_location": r["location"],
                    "delivery_window": r.get("delivery_window"),
                    "expiry_time": d.get("expiry_time"),
                })

        # Vehicles all starting at primary depot
        active_vehicles = [v for v in vehicles if v.get("is_active", True)]
        routes = []
        unserved = []
        unassigned_tasks = list(tasks)

        for v in active_vehicles:
            v_cap = float(v.get("capacity_kg", 100.0))
            v_avail_from = v.get("available_from", "09:00")
            v_avail_to = v.get("available_to", "21:00")

            curr_loc = depot_loc
            curr_stops = []
            curr_load = 0.0

            # Greedy nearest neighbor: find closest unserved task
            while unassigned_tasks:
                best_task_idx = None
                best_dist = float("inf")

                for idx, t in enumerate(unassigned_tasks):
                    # No splits allowed: if quantity exceeds remaining vehicle capacity, cannot fit
                    if curr_load + t["quantity_kg"] > v_cap:
                        continue

                    dist = haversine_distance(curr_loc, t["pickup_location"])
                    if dist < best_dist:
                        best_dist = dist
                        best_task_idx = idx

                if best_task_idx is None:
                    # Vehicle cannot fit any more complete tasks
                    break

                task = unassigned_tasks.pop(best_task_idx)

                # Form pickup and delivery stops
                p_stop = {
                    "type": "pickup",
                    "donation_id": task["donation_id"],
                    "donor_name": task["donor_name"],
                    "kg": task["quantity_kg"],
                    "location": task["pickup_location"],
                    "pickup_window": task["pickup_window"],
                    "expiry_time": task["expiry_time"],
                    "service_min": self.service_time_min,
                }
                d_stop = {
                    "type": "delivery",
                    "request_id": task["request_id"],
                    "receiver_name": task["receiver_name"],
                    "kg": task["quantity_kg"],
                    "location": task["delivery_location"],
                    "delivery_window": task["delivery_window"],
                    "expiry_time": task["expiry_time"],
                    "service_min": self.service_time_min,
                }

                cand_stops = curr_stops + [p_stop, d_stop]

                # Evaluate feasibility
                eval_res = evaluate_route_schedule(
                    stop_sequence=cand_stops,
                    depot_location=depot_loc,
                    vehicle_capacity_kg=v_cap,
                    available_from=v_avail_from,
                    available_to=v_avail_to,
                    distance_lookup_fn=haversine_distance,
                    speed_kmh=self.speed_kmh,
                    service_time_min=self.service_time_min,
                    allow_soft_window=False
                )

                if eval_res.is_feasible:
                    curr_stops = cand_stops
                    curr_load += task["quantity_kg"]
                    curr_loc = task["delivery_location"]
                else:
                    # Reject task for this vehicle and do not retry (naive baseline)
                    unserved.append({
                        "task_id": f"m{task['match_id']}",
                        "quantity_kg": task["quantity_kg"],
                        "reason": f"Baseline failed: {eval_res.failure_reason}"
                    })

            if curr_stops:
                final_eval = evaluate_route_schedule(
                    stop_sequence=curr_stops,
                    depot_location=depot_loc,
                    vehicle_capacity_kg=v_cap,
                    available_from=v_avail_from,
                    available_to=v_avail_to,
                    distance_lookup_fn=haversine_distance,
                    speed_kmh=self.speed_kmh,
                    service_time_min=self.service_time_min,
                    allow_soft_window=False
                )
                routes.append({
                    "vehicle_id": v["id"],
                    "depot_id": primary_depot["id"],
                    "depot_name": primary_depot.get("name", "Single Central Depot"),
                    "stops": curr_stops,
                    "total_distance_km": final_eval.total_distance_km,
                    "total_time_min": final_eval.total_duration_min,
                    "max_load_kg": curr_load
                })

        for rem_t in unassigned_tasks:
            unserved.append({
                "task_id": f"m{rem_t['match_id']}",
                "quantity_kg": rem_t["quantity_kg"],
                "reason": "Exceeded single-depot capacity; splitting not supported in baseline"
            })

        total_dist = sum(r["total_distance_km"] for r in routes)
        total_time_min = sum(r["total_time_min"] for r in routes)
        total_req_kg = sum(t["quantity_kg"] for t in tasks)
        delivered_kg = sum(
            s["kg"] for r in routes for s in r["stops"] if s["type"] == "delivery"
        )
        del_rate = (delivered_kg / total_req_kg * 100.0) if total_req_kg > 0 else 0.0

        return {
            "routes": routes,
            "unserved_tasks": unserved,
            "metrics": {
                "total_distance_km": round(total_dist, 2),
                "total_time_min": round(total_time_min, 1),
                "food_delivered_kg": round(delivered_kg, 2),
                "food_requested_kg": round(total_req_kg, 2),
                "delivery_rate_percent": round(del_rate, 1),
                "unserved_count": len(unserved),
                "computation_time_seconds": round(time.time() - start_time, 4)
            }
        }

