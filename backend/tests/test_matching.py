import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base
from backend.db.models import Donation, Request, MatchRecord, UnmatchedRecord
from backend.matching.matcher import run_urgency_matching, haversine_distance, evaluate_feasibility
from backend.matching.config import scoring_config

@pytest.fixture
def test_db():
    """In-memory SQLite database for isolated unit testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    yield db
    db.close()


def test_haversine_distance():
    """Test Haversine distance calculation between Bangalore MG Road and Hebbal (~8.5 km)."""
    # MG Road: 12.9716, 77.5946; Hebbal: 13.0358, 77.5970
    dist = haversine_distance(12.9716, 77.5946, 13.0358, 77.5970)
    assert 7.0 < dist < 9.0


def test_matching_priority_expiry_ordering(test_db):
    """
    Definition of Done:
    A donation expiring in 2 hours must be matched before an identical one expiring in 10 hours.
    """
    now = datetime(2026, 11, 5, 12, 0, 0)

    # Urgent donation: 2h left
    d_urgent = Donation(
        donor_name="Urgent Caterer",
        food_type="Hot Rice & Curry",
        quantity_kg=50.0,
        remaining_kg=50.0,
        lat=12.9700,
        lng=77.6000,
        ready_time=now,
        expiry_time=now + timedelta(hours=2),
        pickup_window_start="12:00",
        pickup_window_end="14:00",
        status="open"
    )

    # Later donation: 10h left
    d_later = Donation(
        donor_name="Later Caterer",
        food_type="Hot Rice & Curry",
        quantity_kg=50.0,
        remaining_kg=50.0,
        lat=12.9700,
        lng=77.6000,
        ready_time=now,
        expiry_time=now + timedelta(hours=10),
        pickup_window_start="12:00",
        pickup_window_end="14:00",
        status="open"
    )

    # A single request needing 50 kg
    req = Request(
        receiver_name="Central Shelter",
        quantity_kg=50.0,
        remaining_kg=50.0,
        lat=12.9720,
        lng=77.6020,
        delivery_window_start="12:30",
        delivery_window_end="15:00",
        need_level=4,
        status="open",
        created_at=now - timedelta(hours=1)
    )

    test_db.add_all([d_urgent, d_later, req])
    test_db.commit()

    result = run_urgency_matching(db=test_db, current_time=now, cfg=scoring_config)

    # The urgent donation should have been matched with the request!
    assert result["matches_count"] >= 1
    first_match = result["matches"][0]
    assert first_match["donation_id"] == d_urgent.id
    assert first_match["request_id"] == req.id
    assert first_match["allocated_kg"] == 50.0

    # Refresh d_urgent and d_later
    test_db.refresh(d_urgent)
    test_db.refresh(d_later)
    assert d_urgent.remaining_kg == 0.0
    assert d_urgent.status == "matched"
    assert d_later.remaining_kg == 50.0  # Still open


def test_split_delivery_quantities(test_db):
    """
    Test split quantities:
    A single 100 kg donation should be split across two requests (60 kg and 40 kg).
    """
    now = datetime(2026, 11, 5, 12, 0, 0)

    donation = Donation(
        donor_name="Bulk Banquet Hall",
        food_type="Mixed Buffet Trays",
        quantity_kg=100.0,
        remaining_kg=100.0,
        lat=12.9700,
        lng=77.6000,
        ready_time=now,
        expiry_time=now + timedelta(hours=4),
        pickup_window_start="12:00",
        pickup_window_end="15:00",
        status="open"
    )

    req1 = Request(
        receiver_name="Shelter Alpha",
        quantity_kg=60.0,
        remaining_kg=60.0,
        lat=12.9750,
        lng=77.6050,
        delivery_window_start="13:00",
        delivery_window_end="16:00",
        need_level=5,
        status="open",
        created_at=now - timedelta(hours=2)
    )

    req2 = Request(
        receiver_name="Shelter Beta",
        quantity_kg=40.0,
        remaining_kg=40.0,
        lat=12.9800,
        lng=77.6100,
        delivery_window_start="13:00",
        delivery_window_end="16:00",
        need_level=4,
        status="open",
        created_at=now - timedelta(hours=1)
    )

    test_db.add_all([donation, req1, req2])
    test_db.commit()

    result = run_urgency_matching(db=test_db, current_time=now, cfg=scoring_config)

    assert result["matches_count"] == 2
    total_allocated = sum(m["allocated_kg"] for m in result["matches"])
    assert total_allocated == 100.0

    test_db.refresh(donation)
    test_db.refresh(req1)
    test_db.refresh(req2)
    assert donation.remaining_kg == 0.0
    assert donation.status == "matched"
    assert req1.remaining_kg == 0.0
    assert req1.status == "matched"
    assert req2.remaining_kg == 0.0
    assert req2.status == "matched"


def test_feasibility_expired_donation_rejected(test_db):
    """An expired donation must never be matched and must appear in unmatched items."""
    now = datetime(2026, 11, 5, 12, 0, 0)

    # Already expired 1 hour ago
    d_expired = Donation(
        donor_name="Late Cafe",
        food_type="Sandwiches",
        quantity_kg=20.0,
        remaining_kg=20.0,
        lat=12.9700,
        lng=77.6000,
        ready_time=now - timedelta(hours=5),
        expiry_time=now - timedelta(hours=1),
        pickup_window_start="09:00",
        pickup_window_end="11:00",
        status="open"
    )

    req = Request(
        receiver_name="Youth Shelter",
        quantity_kg=20.0,
        remaining_kg=20.0,
        lat=12.9750,
        lng=77.6050,
        delivery_window_start="12:00",
        delivery_window_end="15:00",
        need_level=4,
        status="open",
        created_at=now - timedelta(hours=1)
    )

    test_db.add_all([d_expired, req])
    test_db.commit()

    result = run_urgency_matching(db=test_db, current_time=now, cfg=scoring_config)

    # No matches should be made
    assert result["matches_count"] == 0
    assert result["unmatched_count"] >= 1
    reasons = [u["reason"] for u in result["unmatched"] if u["item_id"] == d_expired.id]
    assert any("expired" in r.lower() for r in reasons)


def test_matching_execution_speed(test_db):
    """
    Definition of Done:
    Matching run must take under 1 second.
    """
    from backend.db.seed import seed_database
    seed_database(test_db, reset=True)

    result = run_urgency_matching(db=test_db, cfg=scoring_config)
    assert result["execution_time_ms"] < 1000.0  # < 1000 ms = 1 second
