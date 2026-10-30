import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.db.database import Base, get_db
from backend.db.seed import seed_database

# Create isolated test database using StaticPool so memory DB is preserved across sessions
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSession()
    seed_database(db, reset=True)
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


def test_auth_registration_and_login(client):
    # Register a new user
    reg_res = client.post("/auth/register", json={
        "username": "newdonor",
        "email": "donor@example.com",
        "password": "securepassword123",
        "role": "donor"
    })
    assert reg_res.status_code == 201
    assert reg_res.json()["username"] == "newdonor"
    assert reg_res.json()["role"] == "donor"

    # Login
    login_res = client.post("/auth/login", json={
        "username": "newdonor",
        "password": "securepassword123"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token is not None

    # Access protected profile
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "newdonor"


def test_donations_crud(client):
    now = datetime.utcnow()
    # Create donation
    create_payload = {
        "donor_name": "Sunrise Bakery",
        "food_type": "Croissants & Buns",
        "quantity_kg": 25.5,
        "location": {"lat": 12.9716, "lng": 77.5946},
        "ready_time": now.isoformat(),
        "expiry_time": (now + timedelta(hours=6)).isoformat(),
        "pickup_window": {"start": "13:00", "end": "16:00"}
    }
    create_res = client.post("/donations", json=create_payload)
    assert create_res.status_code == 201
    donation_data = create_res.json()
    assert donation_data["donor_name"] == "Sunrise Bakery"
    assert donation_data["quantity_kg"] == 25.5
    donation_id = donation_data["id"]

    # Read donation
    get_res = client.get(f"/donations/{donation_id}")
    assert get_res.status_code == 200
    assert get_res.json()["food_type"] == "Croissants & Buns"

    # List donations
    list_res = client.get("/donations")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1


def test_requests_crud(client):
    create_payload = {
        "receiver_name": "Hope Foundation Care",
        "quantity_kg": 50.0,
        "location": {"lat": 12.9344, "lng": 77.6101},
        "delivery_window": {"start": "14:00", "end": "18:00"},
        "need_level": 4
    }
    create_res = client.post("/requests", json=create_payload)
    assert create_res.status_code == 201
    request_data = create_res.json()
    assert request_data["receiver_name"] == "Hope Foundation Care"
    assert request_data["need_level"] == 4
    request_id = request_data["id"]

    # Read request
    get_res = client.get(f"/requests/{request_id}")
    assert get_res.status_code == 200
    assert get_res.json()["quantity_kg"] == 50.0


def test_depots_and_vehicles(client):
    # Create Depot
    depot_res = client.post("/depots", json={
        "name": "East Depot (Whitefield)",
        "location": {"lat": 12.9698, "lng": 77.7499}
    })
    assert depot_res.status_code == 201
    depot_id = depot_res.json()["id"]

    # Create Vehicle assigned to Depot
    veh_res = client.post("/vehicles", json={
        "depot_id": depot_id,
        "capacity_kg": 150.0,
        "available_from": "08:00",
        "available_to": "20:00",
        "is_active": True
    })
    assert veh_res.status_code == 201
    assert veh_res.json()["capacity_kg"] == 150.0


def test_scores_endpoint(client):
    res = client.get("/scores")
    assert res.status_code == 200
    data = res.json()
    assert "donations" in data
    assert "requests" in data
    assert len(data["donations"]) > 0
    assert len(data["requests"]) > 0
    # Verify score structure
    d0 = data["donations"][0]
    assert "expiry_pressure" in d0
    assert "quantity_weight" in d0
    assert "urgency_score" in d0


def test_matching_run_and_results(client):
    # Run matching
    run_res = client.post("/matching/run")
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert "batch_id" in run_data
    assert "matches" in run_data
    assert run_data["matches_count"] > 0
    assert run_data["execution_time_ms"] < 1000.0

    # Retrieve results via GET /matching/results
    results_res = client.get("/matching/results")
    assert results_res.status_code == 200
    results_data = results_res.json()
    assert results_data["matches_count"] == run_data["matches_count"]
    first_match = results_data["matches"][0]
    assert "match_id" in first_match
    assert "donation_id" in first_match
    assert "request_id" in first_match
    assert "allocated_kg" in first_match
    assert "priority_score" in first_match
