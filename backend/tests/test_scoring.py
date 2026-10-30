import pytest
from datetime import datetime, timedelta
from backend.matching.scoring import compute_donation_urgency, compute_request_urgency
from backend.matching.config import scoring_config

def test_donation_urgency_expiry_ranking():
    """Definition of Done Test: A donation expiring in 2 hours must have a strictly higher score than one expiring in 10 hours."""
    now = datetime(2026, 11, 5, 12, 0, 0)

    # 2 hours left
    score_2h = compute_donation_urgency(
        expiry_time=now + timedelta(hours=2),
        ready_time=now,
        quantity_kg=40.0,
        pickup_window_start="12:00",
        pickup_window_end="14:00",
        current_time=now,
        cfg=scoring_config
    )

    # 10 hours left
    score_10h = compute_donation_urgency(
        expiry_time=now + timedelta(hours=10),
        ready_time=now,
        quantity_kg=40.0,
        pickup_window_start="12:00",
        pickup_window_end="14:00",
        current_time=now,
        cfg=scoring_config
    )

    assert score_2h["urgency_score"] > score_10h["urgency_score"]
    assert score_2h["expiry_pressure"] > score_10h["expiry_pressure"]
    assert 0.0 <= score_2h["urgency_score"] <= 1.0
    assert 0.0 <= score_10h["urgency_score"] <= 1.0


def test_donation_urgency_quantity_influence():
    """Larger quantities should yield a higher urgency score when expiry is identical."""
    now = datetime(2026, 11, 5, 12, 0, 0)
    expiry = now + timedelta(hours=5)

    score_small = compute_donation_urgency(
        expiry_time=expiry,
        ready_time=now,
        quantity_kg=15.0,
        pickup_window_start="12:00",
        pickup_window_end="16:00",
        current_time=now,
        cfg=scoring_config
    )

    score_large = compute_donation_urgency(
        expiry_time=expiry,
        ready_time=now,
        quantity_kg=85.0,
        pickup_window_start="12:00",
        pickup_window_end="16:00",
        current_time=now,
        cfg=scoring_config
    )

    assert score_large["urgency_score"] > score_small["urgency_score"]
    assert score_large["quantity_weight"] > score_small["quantity_weight"]


def test_request_urgency_need_level_ranking():
    """Higher need levels (e.g. 5 vs 2) must give higher urgency scores."""
    now = datetime(2026, 11, 5, 12, 0, 0)

    score_high_need = compute_request_urgency(
        need_level=5,
        delivery_window_start="14:00",
        delivery_window_end="17:00",
        created_at=now - timedelta(hours=2),
        current_time=now,
        cfg=scoring_config
    )

    score_low_need = compute_request_urgency(
        need_level=2,
        delivery_window_start="14:00",
        delivery_window_end="17:00",
        created_at=now - timedelta(hours=2),
        current_time=now,
        cfg=scoring_config
    )

    assert score_high_need["urgency_score"] > score_low_need["urgency_score"]
    assert score_high_need["need_level_norm"] > score_low_need["need_level_norm"]
    assert 0.0 <= score_high_need["urgency_score"] <= 1.0
    assert 0.0 <= score_low_need["urgency_score"] <= 1.0


def test_request_urgency_waiting_time():
    """Requests that have been waiting longer should have higher urgency."""
    now = datetime(2026, 11, 5, 12, 0, 0)

    score_recent = compute_request_urgency(
        need_level=4,
        delivery_window_start="14:00",
        delivery_window_end="17:00",
        created_at=now - timedelta(minutes=30),
        current_time=now,
        cfg=scoring_config
    )

    score_waiting = compute_request_urgency(
        need_level=4,
        delivery_window_start="14:00",
        delivery_window_end="17:00",
        created_at=now - timedelta(hours=6),
        current_time=now,
        cfg=scoring_config
    )

    assert score_waiting["urgency_score"] > score_recent["urgency_score"]
    assert score_waiting["waiting_time_norm"] > score_recent["waiting_time_norm"]
