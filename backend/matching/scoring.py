from datetime import datetime, time
from typing import Tuple, Dict, Any, Optional
from backend.matching.config import scoring_config, ScoringConfig

def parse_time_window_hours(start_str: str, end_str: str) -> float:
    """Calculate the duration in hours between start and end time strings formatted as 'HH:MM'."""
    try:
        sh, sm = map(int, start_str.strip().split(":"))
        eh, em = map(int, end_str.strip().split(":"))
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        diff_min = end_min - start_min
        if diff_min <= 0:
            diff_min += 24 * 60  # Crosses midnight or invalid, wrap to 24h cycle
        return max(0.5, diff_min / 60.0)
    except Exception:
        return 4.0  # Default 4 hours if parsing fails


def compute_donation_urgency(
    expiry_time: datetime,
    ready_time: datetime,
    quantity_kg: float,
    pickup_window_start: str,
    pickup_window_end: str,
    current_time: Optional[datetime] = None,
    cfg: ScoringConfig = scoring_config
) -> Dict[str, float]:
    """
    Calculates donation urgency score between 0.0 and 1.0.
    Donation urgency = 0.6 * expiry_pressure + 0.3 * quantity_weight + 0.1 * pickup_window_tightness
    """
    if current_time is None:
        current_time = datetime.utcnow()

    # Expiry pressure: 1 - (time_left / max_shelf_life). Less time left means higher score.
    time_left_hours = (expiry_time - current_time).total_seconds() / 3600.0
    if time_left_hours <= 0:
        expiry_pressure = 1.0  # Already at or past expiry
    elif time_left_hours >= cfg.max_shelf_life_hours:
        expiry_pressure = 0.0
    else:
        expiry_pressure = 1.0 - (time_left_hours / cfg.max_shelf_life_hours)
    expiry_pressure = max(0.0, min(1.0, expiry_pressure))

    # Quantity weight: larger batches get higher priority
    quantity_weight = max(0.0, min(1.0, quantity_kg / cfg.max_reference_quantity_kg))

    # Window tightness: 1 - (window_length / 24h)
    window_length = parse_time_window_hours(pickup_window_start, pickup_window_end)
    pickup_window_tightness = max(0.0, min(1.0, 1.0 - (window_length / cfg.day_hours)))

    # Weighted sum
    urgency_score = (
        cfg.donation_expiry_weight * expiry_pressure +
        cfg.donation_quantity_weight * quantity_weight +
        cfg.donation_pickup_window_weight * pickup_window_tightness
    )
    urgency_score = round(max(0.0, min(1.0, urgency_score)), 4)

    return {
        "time_left_hours": round(time_left_hours, 2),
        "expiry_pressure": round(expiry_pressure, 4),
        "quantity_weight": round(quantity_weight, 4),
        "pickup_window_tightness": round(pickup_window_tightness, 4),
        "urgency_score": urgency_score
    }


def compute_request_urgency(
    need_level: int,
    delivery_window_start: str,
    delivery_window_end: str,
    created_at: datetime,
    current_time: Optional[datetime] = None,
    cfg: ScoringConfig = scoring_config
) -> Dict[str, float]:
    """
    Calculates request urgency score between 0.0 and 1.0.
    Request urgency = 0.5 * need_level_norm + 0.3 * window_tightness + 0.2 * waiting_time_norm
    """
    if current_time is None:
        current_time = datetime.utcnow()

    # Need level normalized: level (1 to 5) / 5
    clamped_need = max(1, min(5, need_level))
    need_level_norm = clamped_need / 5.0

    # Window tightness: 1 - (window_length / 24h)
    window_length = parse_time_window_hours(delivery_window_start, delivery_window_end)
    window_tightness = max(0.0, min(1.0, 1.0 - (window_length / cfg.day_hours)))

    # Waiting time normalized: how long the request has waited
    waiting_time_hours = max(0.0, (current_time - created_at).total_seconds() / 3600.0)
    waiting_time_norm = max(0.0, min(1.0, waiting_time_hours / cfg.max_waiting_time_hours))

    # Weighted sum
    urgency_score = (
        cfg.request_need_level_weight * need_level_norm +
        cfg.request_window_tightness_weight * window_tightness +
        cfg.request_waiting_time_weight * waiting_time_norm
    )
    urgency_score = round(max(0.0, min(1.0, urgency_score)), 4)

    return {
        "need_level_norm": round(need_level_norm, 4),
        "window_tightness": round(window_tightness, 4),
        "waiting_time_norm": round(waiting_time_norm, 4),
        "urgency_score": urgency_score
    }
