from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.db.database import get_db
from backend.db.models import Donation, Request, Depot, Vehicle, MatchRecord, UnmatchedRecord, User
from backend.db.schemas import (
    DonationCreate, DonationUpdate, DonationResponse,
    RequestCreate, RequestUpdate, RequestResponse,
    DepotCreate, DepotUpdate, DepotResponse,
    VehicleCreate, VehicleUpdate, VehicleResponse,
    ScoresResponse, DonationUrgencyScore, RequestUrgencyScore,
    MatchingResultResponse, MatchItem, UnmatchedItem
)
from backend.matching.scoring import compute_donation_urgency, compute_request_urgency
from backend.matching.matcher import run_urgency_matching
from backend.matching.config import scoring_config
from backend.matching.auth import get_current_user

router = APIRouter(tags=["Core & Matching"])

# Serialization Helpers
def donation_to_response(d: Donation) -> dict:
    return {
        "id": d.id,
        "donor_name": d.donor_name,
        "food_type": d.food_type,
        "quantity_kg": d.quantity_kg,
        "remaining_kg": d.remaining_kg,
        "location": {"lat": d.lat, "lng": d.lng},
        "ready_time": d.ready_time,
        "expiry_time": d.expiry_time,
        "pickup_window": {"start": d.pickup_window_start, "end": d.pickup_window_end},
        "status": d.status
    }

def request_to_response(r: Request) -> dict:
    return {
        "id": r.id,
        "receiver_name": r.receiver_name,
        "quantity_kg": r.quantity_kg,
        "remaining_kg": r.remaining_kg,
        "location": {"lat": r.lat, "lng": r.lng},
        "delivery_window": {"start": r.delivery_window_start, "end": r.delivery_window_end},
        "need_level": r.need_level,
        "status": r.status
    }

def depot_to_response(dep: Depot) -> dict:
    return {
        "id": dep.id,
        "name": dep.name,
        "location": {"lat": dep.lat, "lng": dep.lng}
    }

def vehicle_to_response(v: Vehicle) -> dict:
    return {
        "id": v.id,
        "depot_id": v.depot_id,
        "capacity_kg": v.capacity_kg,
        "available_from": v.available_from,
        "available_to": v.available_to,
        "is_active": v.is_active
    }


# ==========================================
# 1. DONATIONS CRUD
# ==========================================

@router.get("/donations", response_model=List[DonationResponse])
def get_donations(
    status: Optional[str] = None,
    food_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Retrieve all food donations, optionally filtered by status or food type."""
    query = db.query(Donation)
    if status:
        query = query.filter(Donation.status == status)
    if food_type:
        query = query.filter(Donation.food_type == food_type)
    donations = query.order_by(Donation.id.asc()).all()
    return [donation_to_response(d) for d in donations]


@router.post("/donations", response_model=DonationResponse, status_code=status.HTTP_201_CREATED)
def create_donation(
    donation_in: DonationCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Create a new surplus food donation."""
    donor_id = current_user.id if current_user else donation_in.donor_id
    
    new_donation = Donation(
        donor_id=donor_id,
        donor_name=donation_in.donor_name,
        food_type=donation_in.food_type,
        quantity_kg=donation_in.quantity_kg,
        remaining_kg=donation_in.quantity_kg,
        lat=donation_in.location.lat,
        lng=donation_in.location.lng,
        ready_time=donation_in.ready_time,
        expiry_time=donation_in.expiry_time,
        pickup_window_start=donation_in.pickup_window.start,
        pickup_window_end=donation_in.pickup_window.end,
        status="open",
        created_at=datetime.utcnow()
    )
    db.add(new_donation)
    db.commit()
    db.refresh(new_donation)
    return donation_to_response(new_donation)


@router.get("/donations/{donation_id}", response_model=DonationResponse)
def get_donation(donation_id: int, db: Session = Depends(get_db)):
    """Fetch details for a specific donation."""
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")
    return donation_to_response(donation)


@router.put("/donations/{donation_id}", response_model=DonationResponse)
def update_donation(donation_id: int, update_in: DonationUpdate, db: Session = Depends(get_db)):
    """Update details of a donation."""
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")

    if update_in.donor_name is not None:
        donation.donor_name = update_in.donor_name
    if update_in.food_type is not None:
        donation.food_type = update_in.food_type
    if update_in.quantity_kg is not None:
        donation.quantity_kg = update_in.quantity_kg
    if update_in.remaining_kg is not None:
        donation.remaining_kg = update_in.remaining_kg
    if update_in.location is not None:
        donation.lat = update_in.location.lat
        donation.lng = update_in.location.lng
    if update_in.ready_time is not None:
        donation.ready_time = update_in.ready_time
    if update_in.expiry_time is not None:
        donation.expiry_time = update_in.expiry_time
    if update_in.pickup_window is not None:
        donation.pickup_window_start = update_in.pickup_window.start
        donation.pickup_window_end = update_in.pickup_window.end
    if update_in.status is not None:
        donation.status = update_in.status

    db.commit()
    db.refresh(donation)
    return donation_to_response(donation)


@router.delete("/donations/{donation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_donation(donation_id: int, db: Session = Depends(get_db)):
    """Delete a donation."""
    donation = db.query(Donation).filter(Donation.id == donation_id).first()
    if not donation:
        raise HTTPException(status_code=404, detail="Donation not found")
    db.delete(donation)
    db.commit()
    return None


# ==========================================
# 2. REQUESTS CRUD
# ==========================================

@router.get("/requests", response_model=List[RequestResponse])
def get_requests(
    status: Optional[str] = None,
    min_need: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Retrieve food requests, optionally filtered by status or need level."""
    query = db.query(Request)
    if status:
        query = query.filter(Request.status == status)
    if min_need:
        query = query.filter(Request.need_level >= min_need)
    requests = query.order_by(Request.id.asc()).all()
    return [request_to_response(r) for r in requests]


@router.post("/requests", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
def create_request(
    request_in: RequestCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Create a new food aid request."""
    receiver_id = current_user.id if current_user else request_in.receiver_id

    new_request = Request(
        receiver_id=receiver_id,
        receiver_name=request_in.receiver_name,
        quantity_kg=request_in.quantity_kg,
        remaining_kg=request_in.quantity_kg,
        lat=request_in.location.lat,
        lng=request_in.location.lng,
        delivery_window_start=request_in.delivery_window.start,
        delivery_window_end=request_in.delivery_window.end,
        need_level=request_in.need_level,
        status="open",
        created_at=datetime.utcnow()
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    return request_to_response(new_request)


@router.get("/requests/{request_id}", response_model=RequestResponse)
def get_request(request_id: int, db: Session = Depends(get_db)):
    """Fetch details for a specific food request."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    return request_to_response(req)


@router.put("/requests/{request_id}", response_model=RequestResponse)
def update_request(request_id: int, update_in: RequestUpdate, db: Session = Depends(get_db)):
    """Update details of a food request."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    if update_in.receiver_name is not None:
        req.receiver_name = update_in.receiver_name
    if update_in.quantity_kg is not None:
        req.quantity_kg = update_in.quantity_kg
    if update_in.remaining_kg is not None:
        req.remaining_kg = update_in.remaining_kg
    if update_in.location is not None:
        req.lat = update_in.location.lat
        req.lng = update_in.location.lng
    if update_in.delivery_window is not None:
        req.delivery_window_start = update_in.delivery_window.start
        req.delivery_window_end = update_in.delivery_window.end
    if update_in.need_level is not None:
        req.need_level = update_in.need_level
    if update_in.status is not None:
        req.status = update_in.status

    db.commit()
    db.refresh(req)
    return request_to_response(req)


@router.delete("/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(request_id: int, db: Session = Depends(get_db)):
    """Delete a food request."""
    req = db.query(Request).filter(Request.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    db.delete(req)
    db.commit()
    return None


# ==========================================
# 3. DEPOTS & VEHICLES CRUD (ADMIN SETUP)
# ==========================================

@router.get("/depots", response_model=List[DepotResponse])
def get_depots(db: Session = Depends(get_db)):
    """List all distribution depots."""
    depots = db.query(Depot).order_by(Depot.id.asc()).all()
    return [depot_to_response(d) for d in depots]


@router.post("/depots", response_model=DepotResponse, status_code=status.HTTP_201_CREATED)
def create_depot(depot_in: DepotCreate, db: Session = Depends(get_db)):
    """Create a new depot."""
    new_depot = Depot(
        name=depot_in.name,
        lat=depot_in.location.lat,
        lng=depot_in.location.lng,
        created_at=datetime.utcnow()
    )
    db.add(new_depot)
    db.commit()
    db.refresh(new_depot)
    return depot_to_response(new_depot)


@router.get("/depots/{depot_id}", response_model=DepotResponse)
def get_depot(depot_id: int, db: Session = Depends(get_db)):
    """Fetch details for a depot."""
    dep = db.query(Depot).filter(Depot.id == depot_id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="Depot not found")
    return depot_to_response(dep)


@router.delete("/depots/{depot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_depot(depot_id: int, db: Session = Depends(get_db)):
    """Delete a depot."""
    dep = db.query(Depot).filter(Depot.id == depot_id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="Depot not found")
    db.delete(dep)
    db.commit()
    return None


@router.get("/vehicles", response_model=List[VehicleResponse])
def get_vehicles(depot_id: Optional[int] = None, db: Session = Depends(get_db)):
    """List all vehicles, optionally filtered by depot."""
    query = db.query(Vehicle)
    if depot_id:
        query = query.filter(Vehicle.depot_id == depot_id)
    vehicles = query.order_by(Vehicle.id.asc()).all()
    return [vehicle_to_response(v) for v in vehicles]


@router.post("/vehicles", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(vehicle_in: VehicleCreate, db: Session = Depends(get_db)):
    """Create a new vehicle assigned to a depot."""
    # Ensure depot exists
    depot = db.query(Depot).filter(Depot.id == vehicle_in.depot_id).first()
    if not depot:
        raise HTTPException(status_code=400, detail=f"Depot with ID {vehicle_in.depot_id} does not exist")

    new_vehicle = Vehicle(
        depot_id=vehicle_in.depot_id,
        capacity_kg=vehicle_in.capacity_kg,
        available_from=vehicle_in.available_from,
        available_to=vehicle_in.available_to,
        is_active=vehicle_in.is_active
    )
    db.add(new_vehicle)
    db.commit()
    db.refresh(new_vehicle)
    return vehicle_to_response(new_vehicle)


@router.get("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Fetch details for a vehicle."""
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle_to_response(v)


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    """Delete a vehicle."""
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    db.delete(v)
    db.commit()
    return None


# ==========================================
# 4. URGENCY SCORES & MATCHING ENGINE
# ==========================================

@router.get("/scores", response_model=ScoresResponse)
def get_current_scores(db: Session = Depends(get_db)):
    """
    Computes and returns current urgency scores and parameter breakdowns
    for all open donations and requests.
    """
    now = datetime.utcnow()

    open_donations = (
        db.query(Donation)
        .filter(Donation.status.in_(["open", "partially_matched"]))
        .filter(Donation.remaining_kg > 0)
        .all()
    )

    donation_scores = []
    for d in open_donations:
        breakdown = compute_donation_urgency(
            expiry_time=d.expiry_time,
            ready_time=d.ready_time,
            quantity_kg=d.remaining_kg,
            pickup_window_start=d.pickup_window_start,
            pickup_window_end=d.pickup_window_end,
            current_time=now,
            cfg=scoring_config
        )
        donation_scores.append(DonationUrgencyScore(
            id=d.id,
            donor_name=d.donor_name,
            food_type=d.food_type,
            quantity_kg=d.remaining_kg,
            time_left_hours=breakdown["time_left_hours"],
            expiry_pressure=breakdown["expiry_pressure"],
            quantity_weight=breakdown["quantity_weight"],
            pickup_window_tightness=breakdown["pickup_window_tightness"],
            urgency_score=breakdown["urgency_score"]
        ))

    open_requests = (
        db.query(Request)
        .filter(Request.status.in_(["open", "partially_matched"]))
        .filter(Request.remaining_kg > 0)
        .all()
    )

    request_scores = []
    for r in open_requests:
        breakdown = compute_request_urgency(
            need_level=r.need_level,
            delivery_window_start=r.delivery_window_start,
            delivery_window_end=r.delivery_window_end,
            created_at=r.created_at,
            current_time=now,
            cfg=scoring_config
        )
        request_scores.append(RequestUrgencyScore(
            id=r.id,
            receiver_name=r.receiver_name,
            quantity_kg=r.remaining_kg,
            need_level=r.need_level,
            need_level_norm=breakdown["need_level_norm"],
            window_tightness=breakdown["window_tightness"],
            waiting_time_norm=breakdown["waiting_time_norm"],
            urgency_score=breakdown["urgency_score"]
        ))

    # Sort descending by urgency
    donation_scores.sort(key=lambda x: x.urgency_score, reverse=True)
    request_scores.sort(key=lambda x: x.urgency_score, reverse=True)

    return ScoresResponse(
        timestamp=now,
        donations=donation_scores,
        requests=request_scores
    )


@router.post("/matching/run", response_model=MatchingResultResponse)
def execute_matching(db: Session = Depends(get_db)):
    """
    Executes the urgency-based priority matching algorithm across open donations and requests.
    Supports partial / split allocations. Saves matches to the database.
    """
    result = run_urgency_matching(db=db, cfg=scoring_config)
    return result


@router.get("/matching/results")
def get_matching_results(batch_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Fetches the latest matches and unmatched items, or those from a specified batch.
    Exposes matches directly to Module 2 (Routing Optimization Engine).
    """
    # If no batch_id specified, find the most recent batch
    if not batch_id:
        latest_match = db.query(MatchRecord).order_by(desc(MatchRecord.created_at)).first()
        if not latest_match:
            # Check unmatched table
            latest_unmatched = db.query(UnmatchedRecord).order_by(desc(UnmatchedRecord.created_at)).first()
            if not latest_unmatched:
                return {
                    "batch_id": None,
                    "matches": [],
                    "unmatched": [],
                    "message": "No matching runs found yet. Trigger /matching/run to compute matches."
                }
            batch_id = latest_unmatched.batch_id
        else:
            batch_id = latest_match.batch_id

    matches = db.query(MatchRecord).filter(MatchRecord.batch_id == batch_id).all()
    unmatched = db.query(UnmatchedRecord).filter(UnmatchedRecord.batch_id == batch_id).all()

    matches_list = []
    for m in matches:
        matches_list.append({
            "match_id": m.match_id,
            "donation_id": m.donation_id,
            "request_id": m.request_id,
            "donor_name": m.donation.donor_name if m.donation else None,
            "receiver_name": m.request.receiver_name if m.request else None,
            "food_type": m.donation.food_type if m.donation else None,
            "allocated_kg": m.allocated_kg,
            "priority_score": m.priority_score,
            "donation_location": {"lat": m.donation.lat, "lng": m.donation.lng} if m.donation else None,
            "request_location": {"lat": m.request.lat, "lng": m.request.lng} if m.request else None,
            "ready_time": m.donation.ready_time.isoformat() if m.donation else None,
            "expiry_time": m.donation.expiry_time.isoformat() if m.donation else None,
            "pickup_window": {"start": m.donation.pickup_window_start, "end": m.donation.pickup_window_end} if m.donation else None,
            "delivery_window": {"start": m.request.delivery_window_start, "end": m.request.delivery_window_end} if m.request else None
        })

    unmatched_list = []
    for u in unmatched:
        unmatched_list.append({
            "item_type": u.item_type,
            "item_id": u.item_id,
            "item_name": u.item_name,
            "unallocated_kg": u.unallocated_kg,
            "reason": u.reason
        })

    return {
        "batch_id": batch_id,
        "matches_count": len(matches_list),
        "unmatched_count": len(unmatched_list),
        "matches": matches_list,
        "unmatched": unmatched_list
    }
