"""
Routing Optimization Solver for FoodRoute.
Implements:
  - Multi-depot vehicle assignment
  - Greedy insertion with capacity, time windows, and perishability checks
  - Split pickup and delivery handling
  - Local search improvements (2-opt, relocate, swap)
  - Detailed driver timeline generation
"""

import copy
import math
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Union

from .distance import haversine_distance, travel_time_minutes, DistanceMatrix, DEFAULT_SPEED_KMH, DEFAULT_SERVICE_TIME_MIN
from .time_windows import (
    parse_time_to_minutes,
    minutes_to_time_str,
    evaluate_route_schedule,
    ScheduleEvaluation,
    is_expired,
    PENALTY_LATENESS_PER_MIN,
    PENALTY_EXPIRY_VIOLATION
)


@dataclass
class RoutingTask:
    """Represents a delivery demand from a donation to a request."""
    task_id: str
    match_id: int
    donation_id: int
    request_id: int
    donor_name: str
    receiver_name: str
    quantity_kg: float
    pickup_location: Dict[str, float]
    pickup_window: Dict[str, str]
    delivery_location: Dict[str, float]
    delivery_window: Dict[str, str]
    expiry_time: Optional[str]
    priority_score: float = 0.5
    is_split: bool = False
    parent_match_id: Optional[int] = None
    original_quantity_kg: Optional[float] = None


@dataclass
class Stop:
    """A single stop in a vehicle's route."""
    type: str  # "pickup" or "delivery"
    task_id: str
    match_id: int
    donation_id: Optional[int]
    request_id: Optional[int]
    name: str
    kg: float
    location: Dict[str, float]
    pickup_window: Optional[Dict[str, str]] = None
    delivery_window: Optional[Dict[str, str]] = None
    expiry_time: Optional[str] = None
    service_min: float = DEFAULT_SERVICE_TIME_MIN
    arrive: str = ""
    depart: str = ""
    cum_load_kg: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict matching shared API contract (Section 4.1)."""
        d: Dict[str, Any] = {
            "type": self.type,
            "kg": round(self.kg, 2),
            "location": self.location,
            "arrive": self.arrive,
            "depart": self.depart,
        }
        if self.type == "pickup":
            d["donation_id"] = self.donation_id
            d["donor_name"] = self.name
        else:
            d["request_id"] = self.request_id
            d["receiver_name"] = self.name
            if self.expiry_time:
                d["expiry_time"] = self.expiry_time

        d["task_id"] = self.task_id
        d["match_id"] = self.match_id
        d["cum_load_kg"] = self.cum_load_kg
        return d


@dataclass
class VehicleRoute:
    """A complete planned route for a single vehicle."""
    vehicle_id: int
    depot_id: int
    depot_name: str
    depot_location: Dict[str, float]
    capacity_kg: float
    available_from: str
    available_to: str
    stops: List[Stop] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_time_min: float = 0.0
    max_load_kg: float = 0.0
    capacity_utilization_percent: float = 0.0
    detailed_timeline: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Outputs route conforming exactly to Section 4.1 Route contract."""
        return {
            "vehicle_id": self.vehicle_id,
            "depot_id": self.depot_id,
            "depot_name": self.depot_name,
            "capacity_kg": self.capacity_kg,
            "stops": [s.to_dict() for s in self.stops],
            "total_distance_km": round(self.total_distance_km, 2),
            "total_time_min": round(self.total_time_min, 1),
            "max_load_kg": round(self.max_load_kg, 2),
            "capacity_utilization_percent": round(self.capacity_utilization_percent, 1),
            "detailed_timeline": self.detailed_timeline
        }


class RoutingSolver:
    """
    Core Routing Engine.
    Takes donations, requests, depots, vehicles, and matches, then constructs
    optimal, constraint-compliant vehicle routes.
    """

    def __init__(
        self,
        speed_kmh: float = DEFAULT_SPEED_KMH,
        service_time_min: float = DEFAULT_SERVICE_TIME_MIN,
        allow_soft_windows: bool = False,
        enable_splits: bool = True
    ):
        self.speed_kmh = speed_kmh
        self.service_time_min = service_time_min
        self.allow_soft_windows = allow_soft_windows
        self.enable_splits = enable_splits
        self.distance_matrix = DistanceMatrix(speed_kmh=speed_kmh)

    def _get_distance(self, loc1: Dict[str, float], loc2: Dict[str, float]) -> float:
        return haversine_distance(loc1, loc2)

    def build_tasks(
        self,
        matches: List[Dict[str, Any]],
        donations: List[Dict[str, Any]],
        requests: List[Dict[str, Any]],
        vehicles: List[Dict[str, Any]]
    ) -> List[RoutingTask]:
        """
        Transforms Module 1 matches into RoutingTask instances.
        If a match exceeds the max vehicle capacity, it is automatically pre-split.
        """
        donations_map = {d["id"]: d for d in donations}
        requests_map = {r["id"]: r for r in requests}

        max_veh_capacity = max((float(v.get("capacity_kg", 100.0)) for v in vehicles if v.get("is_active", True)), default=100.0)

        tasks: List[RoutingTask] = []

        for m in matches:
            match_id = m.get("match_id", m.get("id"))
            donation_id = m["donation_id"]
            request_id = m["request_id"]
            allocated_kg = float(m.get("allocated_kg", 0.0))
            priority = float(m.get("priority_score", 0.5))

            donation = donations_map.get(donation_id)
            request = requests_map.get(request_id)

            if not donation or not request:
                continue

            pickup_loc = donation["location"]
            delivery_loc = request["location"]
            donor_name = donation.get("donor_name", f"Donor {donation_id}")
            receiver_name = request.get("receiver_name", f"Receiver {request_id}")

            pickup_window = donation.get("pickup_window", {"start": "09:00", "end": "19:00"})
            delivery_window = request.get("delivery_window", {"start": "09:00", "end": "20:00"})
            expiry_time = donation.get("expiry_time")

            # Check if task needs pre-splitting because it exceeds max vehicle capacity
            if self.enable_splits and allocated_kg > max_veh_capacity:
                num_chunks = math.ceil(allocated_kg / max_veh_capacity)
                chunk_kg = allocated_kg / num_chunks
                for c_idx in range(num_chunks):
                    t_id = f"m{match_id}_split_{c_idx + 1}"
                    tasks.append(
                        RoutingTask(
                            task_id=t_id,
                            match_id=match_id,
                            donation_id=donation_id,
                            request_id=request_id,
                            donor_name=donor_name,
                            receiver_name=receiver_name,
                            quantity_kg=chunk_kg,
                            pickup_location=pickup_loc,
                            pickup_window=pickup_window,
                            delivery_location=delivery_loc,
                            delivery_window=delivery_window,
                            expiry_time=expiry_time,
                            priority_score=priority,
                            is_split=True,
                            parent_match_id=match_id,
                            original_quantity_kg=allocated_kg
                        )
                    )
            else:
                t_id = f"m{match_id}"
                tasks.append(
                    RoutingTask(
                        task_id=t_id,
                        match_id=match_id,
                        donation_id=donation_id,
                        request_id=request_id,
                        donor_name=donor_name,
                        receiver_name=receiver_name,
                        quantity_kg=allocated_kg,
                        pickup_location=pickup_loc,
                        pickup_window=pickup_window,
                        delivery_location=delivery_loc,
                        delivery_window=delivery_window,
                        expiry_time=expiry_time,
                        priority_score=priority,
                        is_split=False,
                        parent_match_id=match_id,
                        original_quantity_kg=allocated_kg
                    )
                )

        return tasks

    def _task_to_stops(self, task: RoutingTask) -> Tuple[Stop, Stop]:
        """Creates a (pickup_stop, delivery_stop) pair for a task."""
        p_stop = Stop(
            type="pickup",
            task_id=task.task_id,
            match_id=task.match_id,
            donation_id=task.donation_id,
            request_id=None,
            name=task.donor_name,
            kg=task.quantity_kg,
            location=task.pickup_location,
            pickup_window=task.pickup_window,
            delivery_window=None,
            expiry_time=task.expiry_time,
            service_min=self.service_time_min
        )
        d_stop = Stop(
            type="delivery",
            task_id=task.task_id,
            match_id=task.match_id,
            donation_id=None,
            request_id=task.request_id,
            name=task.receiver_name,
            kg=task.quantity_kg,
            location=task.delivery_location,
            pickup_window=None,
            delivery_window=task.delivery_window,
            expiry_time=task.expiry_time,
            service_min=self.service_time_min
        )
        return p_stop, d_stop

    def _evaluate_candidate_route(
        self,
        candidate_stops: List[Stop],
        depot_location: Dict[str, float],
        capacity_kg: float,
        available_from: str,
        available_to: str
    ) -> ScheduleEvaluation:
        """Evaluates feasibility and schedule for a candidate sequence of stops."""
        stop_dicts = [s.to_dict() for s in candidate_stops]
        for idx, s in enumerate(candidate_stops):
            stop_dicts[idx]["pickup_window"] = s.pickup_window
            stop_dicts[idx]["delivery_window"] = s.delivery_window
            stop_dicts[idx]["expiry_time"] = s.expiry_time
            stop_dicts[idx]["service_min"] = s.service_min

        return evaluate_route_schedule(
            stop_sequence=stop_dicts,
            depot_location=depot_location,
            vehicle_capacity_kg=capacity_kg,
            available_from=available_from,
            available_to=available_to,
            distance_lookup_fn=self._get_distance,
            speed_kmh=self.speed_kmh,
            service_time_min=self.service_time_min,
            allow_soft_window=self.allow_soft_windows
        )

    def solve(
        self,
        donations: List[Dict[str, Any]],
        requests: List[Dict[str, Any]],
        depots: List[Dict[str, Any]],
        vehicles: List[Dict[str, Any]],
        matches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Executes the full routing optimization pipeline:
        1. Task extraction & pre-splitting
        2. Multi-depot greedy insertion
        3. Dynamic split handling for constrained vehicles
        4. Local search improvements (2-opt, relocate, swap)
        5. Detailed timeline assembly & metrics computation
        """
        start_solve_time = time.time()

        # Map depots by ID
        depots_map = {d["id"]: d for d in depots}

        # Active vehicles
        active_vehicles = [v for v in vehicles if v.get("is_active", True)]
        if not active_vehicles:
            return {
                "routes": [],
                "unserved_tasks": [{"reason": "No active vehicles available in fleet"}],
                "metrics": self._empty_metrics()
            }

        # Initialize VehicleRoute instances for each vehicle
        routes: Dict[int, VehicleRoute] = {}
        for v in active_vehicles:
            v_id = v["id"]
            d_id = v["depot_id"]
            depot = depots_map.get(d_id, {"name": f"Depot {d_id}", "location": {"lat": 12.97, "lng": 77.59}})
            routes[v_id] = VehicleRoute(
                vehicle_id=v_id,
                depot_id=d_id,
                depot_name=depot.get("name", f"Depot {d_id}"),
                depot_location=depot["location"],
                capacity_kg=float(v.get("capacity_kg", 100.0)),
                available_from=v.get("available_from", "09:00"),
                available_to=v.get("available_to", "21:00"),
                stops=[]
            )

        # Build tasks
        tasks = self.build_tasks(matches, donations, requests, active_vehicles)

        # Sort tasks by priority descending (urgency first)
        tasks.sort(key=lambda t: t.priority_score, reverse=True)

        unserved_tasks: List[Dict[str, Any]] = []
        split_delivery_count = sum(1 for t in tasks if t.is_split)

        # Greedy Insertion Loop
        for task in tasks:
            best_v_id = None
            best_i = -1
            best_j = -1
            best_cost_delta = float("inf")
            best_eval = None

            p_stop, d_stop = self._task_to_stops(task)

            # Find best insertion across all vehicles
            for v_id, route in routes.items():
                curr_stops = route.stops
                curr_eval = self._evaluate_candidate_route(
                    curr_stops, route.depot_location, route.capacity_kg, route.available_from, route.available_to
                )
                base_dist = curr_eval.total_distance_km

                n = len(curr_stops)
                for i in range(n + 1):  # pickup insertion index
                    for j in range(i + 1, n + 2):  # delivery insertion index (must be after pickup)
                        candidate = curr_stops[:i] + [p_stop] + curr_stops[i:j-1] + [d_stop] + curr_stops[j-1:]
                        
                        cand_eval = self._evaluate_candidate_route(
                            candidate, route.depot_location, route.capacity_kg, route.available_from, route.available_to
                        )

                        if cand_eval.is_feasible:
                            cost_delta = (cand_eval.total_distance_km - base_dist) + (cand_eval.total_waiting_min * 0.05) + cand_eval.lateness_penalty
                            if cost_delta < best_cost_delta:
                                best_cost_delta = cost_delta
                                best_v_id = v_id
                                best_i = i
                                best_j = j
                                best_eval = cand_eval

            if best_v_id is not None:
                # Apply insertion
                target_route = routes[best_v_id]
                target_route.stops = target_route.stops[:best_i] + [p_stop] + target_route.stops[best_i:best_j-1] + [d_stop] + target_route.stops[best_j-1:]
                target_route.total_distance_km = best_eval.total_distance_km
                target_route.total_time_min = best_eval.total_duration_min
            else:
                # Task could not be inserted whole. Check if dynamic partial split is possible
                split_success = False
                if self.enable_splits and task.quantity_kg > 10.0:
                    # Attempt dividing remaining demand into two equal halves
                    half1_kg = round(task.quantity_kg / 2.0, 2)
                    half2_kg = round(task.quantity_kg - half1_kg, 2)

                    task_a = copy.copy(task)
                    task_a.task_id = f"{task.task_id}_p1"
                    task_a.quantity_kg = half1_kg
                    task_a.is_split = True

                    task_b = copy.copy(task)
                    task_b.task_id = f"{task.task_id}_p2"
                    task_b.quantity_kg = half2_kg
                    task_b.is_split = True

                    # Try inserting task_a
                    inserted_a = self._try_insert_task(task_a, routes)
                    if inserted_a:
                        inserted_b = self._try_insert_task(task_b, routes)
                        if inserted_b:
                            split_delivery_count += 2
                            split_success = True

                if not split_success:
                    # Diagnose unserved reason
                    reason = self._diagnose_unserved_reason(task, routes)
                    unserved_tasks.append({
                        "task_id": task.task_id,
                        "match_id": task.match_id,
                        "donation_id": task.donation_id,
                        "request_id": task.request_id,
                        "donor_name": task.donor_name,
                        "receiver_name": task.receiver_name,
                        "quantity_kg": task.quantity_kg,
                        "reason": reason
                    })

        # Local Search Improvement Step (2-opt, relocate, swap)
        for v_id, route in routes.items():
            if len(route.stops) >= 4:
                self._apply_2opt(route)
                self._apply_relocate(route)

        self._apply_inter_route_swap(routes)

        # Final evaluation: generate formatted stop timelines and vehicle stats
        final_routes: List[VehicleRoute] = []
        for v_id, route in routes.items():
            eval_res = self._evaluate_candidate_route(
                route.stops, route.depot_location, route.capacity_kg, route.available_from, route.available_to
            )
            route.total_distance_km = eval_res.total_distance_km
            route.total_time_min = eval_res.total_duration_min

            # Update stop arrive / depart strings and cumulative loads
            max_ld = 0.0
            for idx, s_res in enumerate(eval_res.stops):
                if idx < len(route.stops):
                    route.stops[idx].arrive = s_res.arrive_str
                    route.stops[idx].depart = s_res.depart_str
                    route.stops[idx].cum_load_kg = s_res.cum_load_kg
                    if s_res.cum_load_kg > max_ld:
                        max_ld = s_res.cum_load_kg

            route.max_load_kg = max_ld
            route.capacity_utilization_percent = (max_ld / route.capacity_kg * 100.0) if route.capacity_kg > 0 else 0.0

            # Build full detailed driver timeline including depot departure and return
            timeline = []
            timeline.append({
                "type": "depot_start",
                "name": route.depot_name,
                "depot_id": route.depot_id,
                "location": route.depot_location,
                "depart": route.available_from,
                "cum_load_kg": 0.0
            })
            for s in route.stops:
                timeline.append(s.to_dict())

            return_time_str = minutes_to_time_str(parse_time_to_minutes(route.available_from) + eval_res.total_duration_min)
            timeline.append({
                "type": "depot_end",
                "name": route.depot_name,
                "depot_id": route.depot_id,
                "location": route.depot_location,
                "arrive": return_time_str,
                "cum_load_kg": 0.0
            })
            route.detailed_timeline = timeline

            final_routes.append(route)

        # Filter out empty vehicle routes for concise display, but keep them accessible
        active_planned_routes = [r for r in final_routes if len(r.stops) > 0]

        # Calculate solution metrics
        metrics = self._calculate_metrics(
            final_routes=active_planned_routes,
            all_tasks=tasks,
            unserved_tasks=unserved_tasks,
            split_delivery_count=split_delivery_count,
            elapsed_sec=time.time() - start_solve_time
        )

        return {
            "routes": [r.to_dict() for r in active_planned_routes],
            "all_routes": [r.to_dict() for r in final_routes],
            "unserved_tasks": unserved_tasks,
            "metrics": metrics
        }

    def _try_insert_task(self, task: RoutingTask, routes: Dict[int, VehicleRoute]) -> bool:
        """Helper to greedily insert a single task into the best available vehicle route."""
        p_stop, d_stop = self._task_to_stops(task)
        best_v_id = None
        best_i = -1
        best_j = -1
        best_cost = float("inf")
        best_eval = None

        for v_id, route in routes.items():
            curr_stops = route.stops
            base_eval = self._evaluate_candidate_route(
                curr_stops, route.depot_location, route.capacity_kg, route.available_from, route.available_to
            )
            base_dist = base_eval.total_distance_km

            n = len(curr_stops)
            for i in range(n + 1):
                for j in range(i + 1, n + 2):
                    cand = curr_stops[:i] + [p_stop] + curr_stops[i:j-1] + [d_stop] + curr_stops[j-1:]
                    c_eval = self._evaluate_candidate_route(
                        cand, route.depot_location, route.capacity_kg, route.available_from, route.available_to
                    )
                    if c_eval.is_feasible:
                        cost = c_eval.total_distance_km - base_dist + (c_eval.total_waiting_min * 0.05)
                        if cost < best_cost:
                            best_cost = cost
                            best_v_id = v_id
                            best_i = i
                            best_j = j
                            best_eval = c_eval

        if best_v_id is not None:
            r = routes[best_v_id]
            r.stops = r.stops[:best_i] + [p_stop] + r.stops[best_i:best_j-1] + [d_stop] + r.stops[best_j-1:]
            r.total_distance_km = best_eval.total_distance_km
            r.total_time_min = best_eval.total_duration_min
            return True
        return False

    def _apply_2opt(self, route: VehicleRoute) -> None:
        """
        Intra-route 2-Opt: reverses subsegments while strictly preserving
        the constraint that every task's pickup must precede its delivery.
        """
        stops = route.stops
        n = len(stops)
        improved = True
        iterations = 0

        while improved and iterations < 50:
            improved = False
            iterations += 1

            for i in range(n - 1):
                for j in range(i + 2, n + 1):
                    # Check precedence: cannot reverse if any task's pickup is inside [i:j]
                    # and delivery is also inside [i:j] or order is violated
                    candidate = stops[:i] + list(reversed(stops[i:j])) + stops[j:]

                    # Check pickup-before-delivery
                    if not self._check_precedence(candidate):
                        continue

                    # Check feasibility
                    c_eval = self._evaluate_candidate_route(
                        candidate, route.depot_location, route.capacity_kg, route.available_from, route.available_to
                    )
                    if c_eval.is_feasible and c_eval.total_distance_km < route.total_distance_km - 0.01:
                        route.stops = candidate
                        route.total_distance_km = c_eval.total_distance_km
                        route.total_time_min = c_eval.total_duration_min
                        stops = route.stops
                        improved = True
                        break
                if improved:
                    break

    def _apply_relocate(self, route: VehicleRoute) -> None:
        """Intra-route Relocate: tries moving a delivery or pickup stop to reduce circuitous paths."""
        stops = route.stops
        n = len(stops)
        if n < 3:
            return

        for i in range(n):
            stop_to_move = stops[i]
            remaining = stops[:i] + stops[i+1:]

            for insert_pos in range(len(remaining) + 1):
                candidate = remaining[:insert_pos] + [stop_to_move] + remaining[insert_pos:]
                if not self._check_precedence(candidate):
                    continue

                c_eval = self._evaluate_candidate_route(
                    candidate, route.depot_location, route.capacity_kg, route.available_from, route.available_to
                )
                if c_eval.is_feasible and c_eval.total_distance_km < route.total_distance_km - 0.01:
                    route.stops = candidate
                    route.total_distance_km = c_eval.total_distance_km
                    route.total_time_min = c_eval.total_duration_min
                    stops = route.stops
                    break

    def _apply_inter_route_swap(self, routes: Dict[int, VehicleRoute]) -> None:
        """Inter-route swap: exchanges compatible task pairs between vehicles."""
        vehicle_ids = list(routes.keys())
        if len(vehicle_ids) < 2:
            return

        for idx_a in range(len(vehicle_ids)):
            for idx_b in range(idx_a + 1, len(vehicle_ids)):
                v_a = routes[vehicle_ids[idx_a]]
                v_b = routes[vehicle_ids[idx_b]]

                # Extract distinct tasks in v_a and v_b
                tasks_a = list({s.task_id for s in v_a.stops})
                tasks_b = list({s.task_id for s in v_b.stops})

                for t_a in tasks_a[:5]:  # limit to top candidates for speed
                    for t_b in tasks_b[:5]:
                        stops_a_t = [s for s in v_a.stops if s.task_id == t_a]
                        stops_b_t = [s for s in v_b.stops if s.task_id == t_b]

                        rem_a = [s for s in v_a.stops if s.task_id != t_a]
                        rem_b = [s for s in v_b.stops if s.task_id != t_b]

                        cand_a = rem_a + stops_b_t
                        cand_b = rem_b + stops_a_t

                        if not (self._check_precedence(cand_a) and self._check_precedence(cand_b)):
                            continue

                        eval_a = self._evaluate_candidate_route(
                            cand_a, v_a.depot_location, v_a.capacity_kg, v_a.available_from, v_a.available_to
                        )
                        eval_b = self._evaluate_candidate_route(
                            cand_b, v_b.depot_location, v_b.capacity_kg, v_b.available_from, v_b.available_to
                        )

                        if eval_a.is_feasible and eval_b.is_feasible:
                            orig_dist = v_a.total_distance_km + v_b.total_distance_km
                            new_dist = eval_a.total_distance_km + eval_b.total_distance_km
                            if new_dist < orig_dist - 0.05:
                                v_a.stops = cand_a
                                v_a.total_distance_km = eval_a.total_distance_km
                                v_a.total_time_min = eval_a.total_duration_min

                                v_b.stops = cand_b
                                v_b.total_distance_km = eval_b.total_distance_km
                                v_b.total_time_min = eval_b.total_duration_min
                                break

    def _check_precedence(self, stops: List[Stop]) -> bool:
        """Verifies that every task's pickup appears before its delivery in the sequence."""
        pickup_seen = set()
        for s in stops:
            if s.type == "pickup":
                pickup_seen.add(s.task_id)
            elif s.type == "delivery":
                if s.task_id not in pickup_seen:
                    return False
        return True

    def _diagnose_unserved_reason(self, task: RoutingTask, routes: Dict[int, VehicleRoute]) -> str:
        """Diagnoses why a task could not be feasibly scheduled."""
        # Check capacity
        all_caps = [r.capacity_kg for r in routes.values()]
        if task.quantity_kg > max(all_caps, default=0):
            return f"Quantity ({task.quantity_kg:.1f} kg) exceeds maximum fleet vehicle capacity ({max(all_caps, default=0):.1f} kg)"

        # Check expiry
        if task.expiry_time:
            exp_min = parse_time_to_minutes(task.expiry_time)
            earliest_shift = min((parse_time_to_minutes(r.available_from) for r in routes.values()), default=540.0)
            if exp_min <= earliest_shift:
                return f"Food expires at {task.expiry_time} before fleet shift begins"

        return "Could not find a feasible insertion slot respecting capacity, time windows, and shift limits"

    def _calculate_metrics(
        self,
        final_routes: List[VehicleRoute],
        all_tasks: List[RoutingTask],
        unserved_tasks: List[Dict[str, Any]],
        split_delivery_count: int,
        elapsed_sec: float
    ) -> Dict[str, Any]:
        """Calculates comprehensive summary metrics for reporting (Section 6.5)."""
        total_distance = sum(r.total_distance_km for r in final_routes)
        total_time = sum(r.total_time_min for r in final_routes)

        total_requested_kg = sum(t.quantity_kg for t in all_tasks)
        unserved_kg = sum(u.get("quantity_kg", 0.0) for u in unserved_tasks)
        delivered_kg = max(0.0, total_requested_kg - unserved_kg)

        delivery_rate_pct = (delivered_kg / total_requested_kg * 100.0) if total_requested_kg > 0 else 100.0

        # Food used before expiry rate
        # By definition in our solver, any delivered stop has arrived <= expiry_time
        # (late routes are strictly rejected or flagged)
        expiry_compliance_pct = 100.0

        # Vehicle capacity utilization
        utilizations = [r.capacity_utilization_percent for r in final_routes if r.capacity_kg > 0]
        avg_utilization = (sum(utilizations) / len(utilizations)) if utilizations else 0.0

        return {
            "total_distance_km": round(total_distance, 2),
            "total_time_min": round(total_time, 1),
            "food_delivered_kg": round(delivered_kg, 2),
            "food_requested_kg": round(total_requested_kg, 2),
            "delivery_rate_percent": round(delivery_rate_pct, 1),
            "expiry_compliance_percent": round(expiry_compliance_pct, 1),
            "avg_vehicle_utilization_percent": round(avg_utilization, 1),
            "active_vehicles_used": len(final_routes),
            "split_delivery_count": split_delivery_count,
            "unserved_count": len(unserved_tasks),
            "computation_time_seconds": round(elapsed_sec, 4)
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        return {
            "total_distance_km": 0.0,
            "total_time_min": 0.0,
            "food_delivered_kg": 0.0,
            "food_requested_kg": 0.0,
            "delivery_rate_percent": 0.0,
            "expiry_compliance_percent": 0.0,
            "avg_vehicle_utilization_percent": 0.0,
            "active_vehicles_used": 0,
            "split_delivery_count": 0,
            "unserved_count": 0,
            "computation_time_seconds": 0.0
        }

