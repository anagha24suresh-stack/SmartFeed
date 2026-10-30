"""
Time windows and perishability evaluation for FoodRoute.
Handles time normalization, window constraints, early-arrival waiting,
food expiry enforcement, and full route timeline simulation.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, date
from typing import Dict, Any, List, Optional, Tuple, Union

# Default service duration per stop (loading/unloading in minutes)
DEFAULT_SERVICE_TIME_MIN = 15.0

# Large penalty value for soft-window or constraint violations
PENALTY_LATENESS_PER_MIN = 10.0
PENALTY_EXPIRY_VIOLATION = 1_000_000.0


def parse_time_to_minutes(
    time_val: Union[str, int, float, time, datetime],
    base_date: Optional[date] = None
) -> float:
    """
    Parses a time representation into minutes from midnight (0.0 to 1440.0+).
    Supports:
      - String HH:MM or HH:MM:SS (e.g. "14:20", "09:00:00")
      - ISO string (e.g. "2026-11-05T14:00" or "2026-11-05T14:00:00")
      - Numeric minutes (int or float)
      - datetime or time objects
    """
    if isinstance(time_val, (int, float)):
        return float(time_val)

    if isinstance(time_val, time):
        return time_val.hour * 60.0 + time_val.minute + time_val.second / 60.0

    if isinstance(time_val, datetime):
        return time_val.hour * 60.0 + time_val.minute + time_val.second / 60.0

    if isinstance(time_val, str):
        clean_val = time_val.strip()

        # Check for ISO datetime format
        if "T" in clean_val:
            try:
                dt = datetime.fromisoformat(clean_val)
                return dt.hour * 60.0 + dt.minute + dt.second / 60.0
            except ValueError:
                pass

        # Check for date space time "2026-11-05 14:00:00"
        if " " in clean_val and ("-" in clean_val or "/" in clean_val):
            try:
                time_part = clean_val.split(" ")[1]
                parts = [float(p) for p in time_part.split(":")]
                if len(parts) == 2:
                    return parts[0] * 60.0 + parts[1]
                elif len(parts) >= 3:
                    return parts[0] * 60.0 + parts[1] + parts[2] / 60.0
            except Exception:
                pass

        # Standard "HH:MM" or "HH:MM:SS"
        parts = clean_val.split(":")
        if len(parts) == 2:
            return float(parts[0]) * 60.0 + float(parts[1])
        elif len(parts) >= 3:
            return float(parts[0]) * 60.0 + float(parts[1]) + float(parts[2]) / 60.0

    raise ValueError(f"Unable to parse time value into minutes: {time_val} (type: {type(time_val)})")


def minutes_to_time_str(minutes: float) -> str:
    """
    Converts minutes from midnight to standard "HH:MM" 24-hour time string.
    Example: 860.0 -> "14:20"
    """
    total_minutes = int(round(minutes)) % (24 * 60)
    hours = total_minutes // 60
    mins = total_minutes % 60
    return f"{hours:02d}:{mins:02d}"


@dataclass
class TimeWindow:
    """Represents a time window [start, end] in minutes from midnight."""
    start_minutes: float
    end_minutes: float
    start_str: str = ""
    end_str: str = ""

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]], default_start: float = 0.0, default_end: float = 1440.0) -> "TimeWindow":
        """Builds a TimeWindow from a dictionary with 'start' and 'end' keys."""
        if not data:
            return cls(
                start_minutes=default_start,
                end_minutes=default_end,
                start_str=minutes_to_time_str(default_start),
                end_str=minutes_to_time_str(default_end)
            )

        start_val = data.get("start", default_start)
        end_val = data.get("end", default_end)

        s_min = parse_time_to_minutes(start_val)
        e_min = parse_time_to_minutes(end_val)

        return cls(
            start_minutes=s_min,
            end_minutes=e_min,
            start_str=str(start_val) if isinstance(start_val, str) else minutes_to_time_str(s_min),
            end_str=str(end_val) if isinstance(end_val, str) else minutes_to_time_str(e_min)
        )

    def is_within(self, arrival_minutes: float) -> bool:
        """True if arrival occurs at or before the window close."""
        return arrival_minutes <= self.end_minutes + 1e-4

    def lateness(self, arrival_minutes: float) -> float:
        """Returns minutes late beyond window end, or 0.0 if on time."""
        if arrival_minutes > self.end_minutes:
            return arrival_minutes - self.end_minutes
        return 0.0

    def waiting_time(self, arrival_minutes: float) -> float:
        """Returns minutes vehicle must wait if it arrives before the window opens."""
        if arrival_minutes < self.start_minutes:
            return self.start_minutes - arrival_minutes
        return 0.0


def is_within_window(arrival_minutes: float, window: TimeWindow) -> bool:
    """Checks if arrival is on or before window end."""
    return window.is_within(arrival_minutes)


def is_expired(delivery_arrival_minutes: float, expiry_minutes: float) -> bool:
    """
    Returns True if delivery arrival occurs strictly after food expiry time.
    Food delivered after expiry is considered spoiled and unacceptable.
    """
    return delivery_arrival_minutes > (expiry_minutes + 1e-4)


@dataclass
class ScheduleStopResult:
    """Timeline details for an evaluated route stop."""
    stop_index: int
    stop_type: str  # "depot_start", "pickup", "delivery", "depot_end"
    location_id: str
    location: Dict[str, float]
    arrival_min: float
    wait_min: float
    service_min: float
    departure_min: float
    arrive_str: str
    depart_str: str
    is_late: bool
    lateness_min: float
    is_expired: bool
    cum_load_kg: float
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleEvaluation:
    """Overall evaluation of a route schedule."""
    is_feasible: bool
    total_distance_km: float
    total_driving_min: float
    total_waiting_min: float
    total_service_min: float
    total_duration_min: float
    lateness_penalty: float
    expiry_violation_count: int
    capacity_violation_kg: float
    stops: List[ScheduleStopResult]
    failure_reason: Optional[str] = None


def evaluate_route_schedule(
    stop_sequence: List[Dict[str, Any]],
    depot_location: Dict[str, float],
    vehicle_capacity_kg: float,
    available_from: str = "09:00",
    available_to: str = "21:00",
    distance_lookup_fn = None,
    speed_kmh: float = 30.0,
    service_time_min: float = DEFAULT_SERVICE_TIME_MIN,
    allow_soft_window: bool = False
) -> ScheduleEvaluation:
    """
    Simulates and evaluates the complete schedule for a vehicle route starting and ending at a depot.

    Args:
        stop_sequence: Ordered list of stop dicts (pickups and deliveries).
        depot_location: {"lat": ..., "lng": ...}
        vehicle_capacity_kg: Max capacity of vehicle.
        available_from: Vehicle shift start time (e.g. "09:00").
        available_to: Vehicle shift end time (e.g. "21:00").
        distance_lookup_fn: Callable (loc1, loc2) -> distance_km.
        speed_kmh: Average travel speed in km/h.
        service_time_min: Standard service time per stop in minutes.
        allow_soft_window: If True, late arrivals incur penalty instead of hard failure.

    Returns:
        ScheduleEvaluation containing feasibility, times, and stop timelines.
    """
    shift_start_min = parse_time_to_minutes(available_from)
    shift_end_min = parse_time_to_minutes(available_to)

    if not stop_sequence:
        # Empty route: vehicle stays at depot
        return ScheduleEvaluation(
            is_feasible=True,
            total_distance_km=0.0,
            total_driving_min=0.0,
            total_waiting_min=0.0,
            total_service_min=0.0,
            total_duration_min=0.0,
            lateness_penalty=0.0,
            expiry_violation_count=0,
            capacity_violation_kg=0.0,
            stops=[]
        )

    # If first stop has an open window later than shift_start, we can depart so as to arrive just on time
    # But by default vehicle can depart at shift_start_min or adjusted departure
    total_distance_km = 0.0
    total_driving_min = 0.0
    total_waiting_min = 0.0
    total_service_min = 0.0
    cum_load = 0.0
    max_load_observed = 0.0

    eval_stops: List[ScheduleStopResult] = []
    current_time_min = shift_start_min
    prev_loc = depot_location

    total_lateness_min = 0.0
    expiry_violations = 0

    for idx, stop in enumerate(stop_sequence):
        stop_loc = stop["location"]
        dist = distance_lookup_fn(prev_loc, stop_loc) if distance_lookup_fn else 0.0
        travel_min = (dist / speed_kmh) * 60.0 if speed_kmh > 0 else 0.0

        arrival_min = current_time_min + travel_min
        total_distance_km += dist
        total_driving_min += travel_min

        # Time window handling
        tw_data = stop.get("pickup_window") if stop.get("type") == "pickup" else stop.get("delivery_window")
        window = TimeWindow.from_dict(tw_data, default_start=shift_start_min, default_end=shift_end_min)

        wait_min = window.waiting_time(arrival_min)
        total_waiting_min += wait_min

        # Actual service start is max(arrival, window.start)
        service_start_min = arrival_min + wait_min
        s_time = float(stop.get("service_min", service_time_min))
        total_service_min += s_time
        departure_min = service_start_min + s_time

        # Lateness check
        late_min = window.lateness(arrival_min)
        is_late = late_min > 1e-4
        if is_late:
            total_lateness_min += late_min

        # Food expiry check (crucial for food rescue: delivery must be before food expires)
        is_exp = False
        expiry_val = stop.get("expiry_time")
        if stop.get("type") == "delivery" and expiry_val:
            exp_min = parse_time_to_minutes(expiry_val)
            if is_expired(arrival_min, exp_min):
                is_exp = True
                expiry_violations += 1

        # Cumulative load check
        stop_kg = float(stop.get("kg", 0.0))
        if stop.get("type") == "pickup":
            cum_load += stop_kg
        elif stop.get("type") == "delivery":
            cum_load -= stop_kg
            if cum_load < -1e-4:
                # Delivering more than picked up
                pass

        if cum_load > max_load_observed:
            max_load_observed = cum_load

        eval_stops.append(
            ScheduleStopResult(
                stop_index=idx,
                stop_type=stop.get("type", "stop"),
                location_id=str(stop.get("donation_id") or stop.get("request_id") or idx),
                location=stop_loc,
                arrival_min=arrival_min,
                wait_min=wait_min,
                service_min=s_time,
                departure_min=departure_min,
                arrive_str=minutes_to_time_str(arrival_min),
                depart_str=minutes_to_time_str(departure_min),
                is_late=is_late,
                lateness_min=late_min,
                is_expired=is_exp,
                cum_load_kg=round(cum_load, 2),
                meta=stop
            )
        )

        current_time_min = departure_min
        prev_loc = stop_loc

    # Return travel back to depot
    return_dist = distance_lookup_fn(prev_loc, depot_location) if distance_lookup_fn else 0.0
    return_travel_min = (return_dist / speed_kmh) * 60.0 if speed_kmh > 0 else 0.0

    depot_return_min = current_time_min + return_travel_min
    total_distance_km += return_dist
    total_driving_min += return_travel_min

    # Check shift end feasibility
    return_late_min = max(0.0, depot_return_min - shift_end_min)
    if return_late_min > 1e-4:
        total_lateness_min += return_late_min

    capacity_violation = max(0.0, max_load_observed - vehicle_capacity_kg)
    total_duration_min = depot_return_min - shift_start_min

    # Feasibility decision
    is_feasible = True
    failure_reason = None

    if capacity_violation > 1e-4:
        is_feasible = False
        failure_reason = f"Vehicle capacity exceeded by {capacity_violation:.1f} kg (Max load: {max_load_observed:.1f} kg, Capacity: {vehicle_capacity_kg:.1f} kg)"
    elif expiry_violations > 0:
        is_feasible = False
        failure_reason = f"Perishability violation: {expiry_violations} delivery stop(s) arrived after food expiry"
    elif not allow_soft_window and total_lateness_min > 1e-4:
        is_feasible = False
        failure_reason = f"Time window violation: total lateness of {total_lateness_min:.1f} minutes"

    lateness_penalty = (total_lateness_min * PENALTY_LATENESS_PER_MIN) + (expiry_violations * PENALTY_EXPIRY_VIOLATION)

    return ScheduleEvaluation(
        is_feasible=is_feasible,
        total_distance_km=round(total_distance_km, 2),
        total_driving_min=round(total_driving_min, 2),
        total_waiting_min=round(total_waiting_min, 2),
        total_service_min=round(total_service_min, 2),
        total_duration_min=round(total_duration_min, 2),
        lateness_penalty=round(lateness_penalty, 2),
        expiry_violation_count=expiry_violations,
        capacity_violation_kg=round(capacity_violation, 2),
        stops=eval_stops,
        failure_reason=failure_reason
    )

