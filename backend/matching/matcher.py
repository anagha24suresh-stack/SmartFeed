import math
import uuid
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from backend.matching.config import scoring_config, ScoringConfig
from backend.matching.scoring import compute_donation_urgency, compute_request_urgency
from backend.db.models import Donation, Request, MatchRecord, UnmatchedRecord

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Computes great-circle distance in kilometers between two GPS coordinates using the Haversine formula.
    """
    R = 6371.0  # Earth's radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def evaluate_feasibility(
    donation: Donation,
    request: Request,
    current_time: datetime,
    cfg: ScoringConfig = scoring_config
) -> Tuple[float, str]:
    """
    Evaluates whether food from a donation can arrive at the receiver before expiring.
    Returns (feasibility_score, reason).
    feasibility is 0 if food would expire before arrival; otherwise 1 - (distance_penalty * distance).
    """
    # Expiry check
    if donation.expiry_time <= current_time:
        return 0.0, "Donation has already expired"

    # Haversine distance
    dist_km = haversine_distance(donation.lat, donation.lng, request.lat, request.lng)

    # Transit time estimate
    transit_hours = dist_km / max(5.0, cfg.average_vehicle_speed_kmh)
    estimated_arrival = current_time + timedelta(hours=transit_hours)

    if estimated_arrival >= donation.expiry_time:
        return 0.0, f"Expires before reachable (transit ~{transit_hours:.1f}h exceeds shelf life)"

    # Penalty for large travel distance to prefer nearby distribution when possible
    penalty = cfg.distance_penalty_factor * dist_km
    feasibility = max(cfg.min_feasibility_score, 1.0 - penalty)

    return round(feasibility, 4), "Feasible"


def run_urgency_matching(
    db: Session,
    current_time: Optional[datetime] = None,
    cfg: ScoringConfig = scoring_config
) -> Dict[str, Any]:
    """
    Executes the urgency-based matching algorithm with partial / split allocations.
    
    Algorithm:
    1. Score all open donations and requests by urgency.
    2. Sort donations by urgency (highest first). Sort requests by urgency (highest first).
    3. For each candidate pair, compute priority = donation_urgency * request_urgency * feasibility.
    4. Allocate min(remaining_donation, remaining_request) allowing partial splits.
    5. Repeat until no feasible pairs remain.
    6. Record unmatched remnants with explanatory reasons.
    """
    start_time = time.time()
    if current_time is None:
        current_time = datetime.utcnow()

    batch_id = str(uuid.uuid4())[:8]

    # Query all active donations and requests with remaining quantity
    open_donations = (
        db.query(Donation)
        .filter(Donation.status.in_(["open", "partially_matched"]))
        .filter(Donation.remaining_kg > 0.001)
        .all()
    )

    open_requests = (
        db.query(Request)
        .filter(Request.status.in_(["open", "partially_matched"]))
        .filter(Request.remaining_kg > 0.001)
        .all()
    )

    # 1. Score each item
    donation_scores: Dict[int, float] = {}
    for d in open_donations:
        score_info = compute_donation_urgency(
            expiry_time=d.expiry_time,
            ready_time=d.ready_time,
            quantity_kg=d.remaining_kg,
            pickup_window_start=d.pickup_window_start,
            pickup_window_end=d.pickup_window_end,
            current_time=current_time,
            cfg=cfg
        )
        donation_scores[d.id] = score_info["urgency_score"]

    request_scores: Dict[int, float] = {}
    for r in open_requests:
        score_info = compute_request_urgency(
            need_level=r.need_level,
            delivery_window_start=r.delivery_window_start,
            delivery_window_end=r.delivery_window_end,
            created_at=r.created_at,
            current_time=current_time,
            cfg=cfg
        )
        request_scores[r.id] = score_info["urgency_score"]

    # 2. Build candidate pairs with compatibility score
    candidate_pairs = []
    infeasibility_reasons: Dict[Tuple[int, int], str] = {}

    for d in open_donations:
        d_urgency = donation_scores[d.id]
        for r in open_requests:
            r_urgency = request_scores[r.id]
            feasibility, reason = evaluate_feasibility(d, r, current_time, cfg)
            
            if feasibility > 0.0:
                priority = round(d_urgency * r_urgency * feasibility, 4)
                candidate_pairs.append({
                    "priority": priority,
                    "donation": d,
                    "request": r,
                    "feasibility": feasibility
                })
            else:
                infeasibility_reasons[(d.id, r.id)] = reason

    # Sort candidate pairs by priority descending
    candidate_pairs.sort(key=lambda x: x["priority"], reverse=True)

    matches_to_save: List[MatchRecord] = []
    match_items_output: List[Dict[str, Any]] = []
    total_allocated_kg = 0.0
    match_counter = 1

    # Keep track of working remaining quantities to support split allocations
    remaining_donations = {d.id: d.remaining_kg for d in open_donations}
    remaining_requests = {r.id: r.remaining_kg for r in open_requests}

    # 3. Greedy allocation with splits
    for pair in candidate_pairs:
        d = pair["donation"]
        r = pair["request"]
        p = pair["priority"]

        available_d = remaining_donations.get(d.id, 0.0)
        needed_r = remaining_requests.get(r.id, 0.0)

        if available_d > 0.001 and needed_r > 0.001:
            alloc_kg = round(min(available_d, needed_r), 2)
            if alloc_kg <= 0:
                continue

            remaining_donations[d.id] -= alloc_kg
            remaining_requests[r.id] -= alloc_kg
            total_allocated_kg += alloc_kg

            record = MatchRecord(
                match_id=match_counter,
                batch_id=batch_id,
                donation_id=d.id,
                request_id=r.id,
                allocated_kg=alloc_kg,
                priority_score=p,
                created_at=datetime.utcnow()
            )
            matches_to_save.append(record)

            match_items_output.append({
                "match_id": match_counter,
                "donation_id": d.id,
                "request_id": r.id,
                "donor_name": d.donor_name,
                "receiver_name": r.receiver_name,
                "food_type": d.food_type,
                "allocated_kg": alloc_kg,
                "priority_score": p
            })
            match_counter += 1

    # Update database models with new remaining quantities and status
    for d in open_donations:
        rem = round(remaining_donations[d.id], 2)
        d.remaining_kg = rem
        if rem <= 0.001:
            d.status = "matched"
        elif rem < d.quantity_kg:
            d.status = "partially_matched"
        # If no quantity was matched, status remains open

    for r in open_requests:
        rem = round(remaining_requests[r.id], 2)
        r.remaining_kg = rem
        if rem <= 0.001:
            r.status = "matched"
        elif rem < r.quantity_kg:
            r.status = "partially_matched"

    # Save matches
    for m in matches_to_save:
        db.add(m)

    # 4. Identify unmatched / surplus items
    unmatched_records_to_save: List[UnmatchedRecord] = []
    unmatched_items_output: List[Dict[str, Any]] = []

    for d in open_donations:
        unalloc = round(remaining_donations[d.id], 2)
        if unalloc > 0.001:
            # Check reasons
            reason = "No matching demand available for surplus quantity"
            if d.expiry_time <= current_time:
                reason = "Food expired before match"
            else:
                # Check if there were requests that couldn't be reached
                reasons_list = [infeasibility_reasons.get((d.id, r.id)) for r in open_requests if (d.id, r.id) in infeasibility_reasons]
                if reasons_list:
                    reason = reasons_list[0]

            unmatched_rec = UnmatchedRecord(
                batch_id=batch_id,
                item_type="donation",
                item_id=d.id,
                item_name=d.donor_name,
                unallocated_kg=unalloc,
                reason=reason,
                created_at=datetime.utcnow()
            )
            unmatched_records_to_save.append(unmatched_rec)
            unmatched_items_output.append({
                "item_type": "donation",
                "item_id": d.id,
                "item_name": d.donor_name,
                "unallocated_kg": unalloc,
                "reason": reason
            })

    for r in open_requests:
        unalloc = round(remaining_requests[r.id], 2)
        if unalloc > 0.001:
            reason = "Insufficient surplus donations available within time window"
            unmatched_rec = UnmatchedRecord(
                batch_id=batch_id,
                item_type="request",
                item_id=r.id,
                item_name=r.receiver_name,
                unallocated_kg=unalloc,
                reason=reason,
                created_at=datetime.utcnow()
            )
            unmatched_records_to_save.append(unmatched_rec)
            unmatched_items_output.append({
                "item_type": "request",
                "item_id": r.id,
                "item_name": r.receiver_name,
                "unallocated_kg": unalloc,
                "reason": reason
            })

    for u in unmatched_records_to_save:
        db.add(u)

    db.commit()

    exec_time_ms = round((time.time() - start_time) * 1000.0, 2)

    return {
        "batch_id": batch_id,
        "executed_at": datetime.utcnow(),
        "execution_time_ms": exec_time_ms,
        "total_donations_evaluated": len(open_donations),
        "total_requests_evaluated": len(open_requests),
        "total_allocated_kg": round(total_allocated_kg, 2),
        "matches_count": len(match_items_output),
        "unmatched_count": len(unmatched_items_output),
        "matches": match_items_output,
        "unmatched": unmatched_items_output
    }
