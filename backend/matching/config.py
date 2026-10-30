"""Configuration weights and parameters for urgency scoring and matching.
Stored in a dedicated file so the team can easily tune parameters.
"""

from pydantic import BaseModel

class ScoringConfig(BaseModel):
    # Donation weights (sum = 1.0)
    donation_expiry_weight: float = 0.6
    donation_quantity_weight: float = 0.3
    donation_pickup_window_weight: float = 0.1

    # Request weights (sum = 1.0)
    request_need_level_weight: float = 0.5
    request_window_tightness_weight: float = 0.3
    request_waiting_time_weight: float = 0.2

    # Reference constants
    max_shelf_life_hours: float = 24.0   # Reference shelf life in hours
    max_reference_quantity_kg: float = 100.0  # Reference quantity for normalization
    max_waiting_time_hours: float = 12.0  # Reference waiting time before fulfillment
    day_hours: float = 24.0

    # Matching & Feasibility parameters
    average_vehicle_speed_kmh: float = 30.0  # Speed for transit time estimation
    distance_penalty_factor: float = 0.005  # Slight preference for closer matches
    min_feasibility_score: float = 0.05      # Minimum non-zero feasibility if within time


# Global instance of scoring configuration
scoring_config = ScoringConfig()
