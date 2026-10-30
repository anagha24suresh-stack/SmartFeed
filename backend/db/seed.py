import datetime
from sqlalchemy.orm import Session
from backend.db.database import SessionLocal, engine, Base
from backend.db.models import User, Depot, Vehicle, Donation, Request, MatchRecord, UnmatchedRecord
from backend.matching.auth import get_password_hash

def seed_database(db: Session, reset: bool = False):
    """
    Populates database with realistic initial seed data:
    - 3 Users (Admin, Donor, Receiver)
    - 3 Depots (Bangalore North, Central, South)
    - 5 Fleet Vehicles
    - 12 Surplus Food Donations with diverse expiry times & food types
    - 12 Food Aid Requests with diverse need levels (1 to 5)
    """
    if reset:
        # Drop all tables and recreate
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    else:
        Base.metadata.create_all(bind=engine)

    # Check if already seeded
    existing_depots = db.query(Depot).count()
    if existing_depots >= 3 and not reset:
        print("[Seed] Database already populated with seed data. Skipping.")
        return

    print("[Seed] Seeding database with realistic Bangalore test data...")

    # 1. Users
    admin_user = User(
        username="admin",
        email="admin@foodroute.org",
        hashed_password=get_password_hash("admin123"),
        role="admin"
    )
    donor_user = User(
        username="greenleaf",
        email="donations@greenleaf.com",
        hashed_password=get_password_hash("donor123"),
        role="donor"
    )
    receiver_user = User(
        username="hopeshelter",
        email="aid@hopeshelter.org",
        hashed_password=get_password_hash("receiver123"),
        role="receiver"
    )
    db.add_all([admin_user, donor_user, receiver_user])
    db.flush()

    # 2. Depots (Bangalore Hubs)
    depot_north = Depot(name="North Bangalore Depot (Hebbal)", lat=13.0358, lng=77.5970)
    depot_central = Depot(name="Central Depot (MG Road)", lat=12.9716, lng=77.5946)
    depot_south = Depot(name="South Depot (HSR Layout)", lat=12.9141, lng=77.6387)

    db.add_all([depot_north, depot_central, depot_south])
    db.flush()

    # 3. Fleet Vehicles
    v1 = Vehicle(depot_id=depot_north.id, capacity_kg=120.0, available_from="08:00", available_to="20:00")
    v2 = Vehicle(depot_id=depot_north.id, capacity_kg=80.0, available_from="09:00", available_to="21:00")
    v3 = Vehicle(depot_id=depot_central.id, capacity_kg=150.0, available_from="07:30", available_to="19:30")
    v4 = Vehicle(depot_id=depot_central.id, capacity_kg=100.0, available_from="10:00", available_to="22:00")
    v5 = Vehicle(depot_id=depot_south.id, capacity_kg=140.0, available_from="08:00", available_to="20:30")

    db.add_all([v1, v2, v3, v4, v5])
    db.flush()

    # Base reference time
    now = datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    # 4. Donations (12 items with varying urgency and expiry windows)
    donations = [
        Donation(
            donor_id=donor_user.id,
            donor_name="Green Leaf Restaurant",
            food_type="Cooked Meals (Rice, Curry & Dal)",
            quantity_kg=40.0,
            remaining_kg=40.0,
            lat=12.9750,
            lng=77.6050,  # Indiranagar
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=2.5),  # HIGH URGENCY: Expiring in 2.5h!
            pickup_window_start="12:00",
            pickup_window_end="14:30",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Taj Gateway Banquets",
            food_type="Buffet Trays (Biryani & Paneer)",
            quantity_kg=65.0,
            remaining_kg=65.0,
            lat=12.9719,
            lng=77.6010,  # Residency Road
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=3.0),  # HIGH URGENCY: Expiring in 3h
            pickup_window_start="13:00",
            pickup_window_end="15:30",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Daily Bread Artisanal Bakery",
            food_type="Fresh Bread & Sandwiches",
            quantity_kg=25.0,
            remaining_kg=25.0,
            lat=12.9352,
            lng=77.6245,  # Koramangala
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=6.0),  # MEDIUM URGENCY
            pickup_window_start="11:00",
            pickup_window_end="16:00",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Metro Fresh Supermarket",
            food_type="Fresh Vegetables & Greens",
            quantity_kg=80.0,
            remaining_kg=80.0,
            lat=13.0012,
            lng=77.5714,  # Malleshwaram
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=14.0),
            pickup_window_start="10:00",
            pickup_window_end="18:00",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Infosys Campus Foodcourt",
            food_type="Cooked Meals (Roti, Sabzi)",
            quantity_kg=90.0,
            remaining_kg=90.0,
            lat=12.8452,
            lng=77.6602,  # Electronic City
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=4.0),  # HIGH URGENCY
            pickup_window_start="13:30",
            pickup_window_end="16:30",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Milky Way Dairy Mart",
            food_type="Milk, Yogurt & Paneer",
            quantity_kg=35.0,
            remaining_kg=35.0,
            lat=12.9279,
            lng=77.5852,  # Jayanagar
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=8.0),
            pickup_window_start="09:00",
            pickup_window_end="15:00",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Orchid Convention Hall",
            food_type="Wedding Feast Surplus (Mixed)",
            quantity_kg=110.0,
            remaining_kg=110.0,
            lat=13.0280,
            lng=77.5409,  # Yeshwanthpur
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=3.5),  # HIGH URGENCY
            pickup_window_start="14:00",
            pickup_window_end="17:00",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Organic Roots Farm Store",
            food_type="Apples, Bananas & Seasonal Fruit",
            quantity_kg=50.0,
            remaining_kg=50.0,
            lat=12.9784,
            lng=77.6408,  # Indiranagar 100ft Road
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=20.0),
            pickup_window_start="10:00",
            pickup_window_end="19:00",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Spice Terrace Kitchen",
            food_type="Rice & Vegetable Pulao",
            quantity_kg=30.0,
            remaining_kg=30.0,
            lat=12.9601,
            lng=77.6483,  # Domlur
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=5.0),
            pickup_window_start="12:30",
            pickup_window_end="15:30",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="BigBasket Fulfillment Hub",
            food_type="Packaged Cereals & Pulses",
            quantity_kg=120.0,
            remaining_kg=120.0,
            lat=12.9904,
            lng=77.6872,  # Whitefield
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=48.0),  # Low urgency shelf-stable
            pickup_window_start="08:00",
            pickup_window_end="20:00",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Saffron Dine Catering",
            food_type="Cooked Meals (South Indian Thali)",
            quantity_kg=45.0,
            remaining_kg=45.0,
            lat=12.9116,
            lng=77.6012,  # BTM Layout
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=2.0),  # CRITICAL: 2h left!
            pickup_window_start="13:00",
            pickup_window_end="14:30",
            status="open"
        ),
        Donation(
            donor_id=donor_user.id,
            donor_name="Corner House Bakery",
            food_type="Pastries, Buns & Muffins",
            quantity_kg=20.0,
            remaining_kg=20.0,
            lat=12.9615,
            lng=77.5950,  # Richmond Town
            ready_time=now,
            expiry_time=now + datetime.timedelta(hours=7.0),
            pickup_window_start="14:00",
            pickup_window_end="18:00",
            status="open"
        )
    ]
    db.add_all(donations)
    db.flush()

    # 5. Requests (12 items with varying need levels and delivery windows)
    requests = [
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Hope Night Shelter",
            quantity_kg=60.0,
            remaining_kg=60.0,
            lat=12.9344,
            lng=77.6101,  # Adugodi
            delivery_window_start="14:00",
            delivery_window_end="17:00",
            need_level=5,  # HIGHEST NEED
            status="open",
            created_at=now - datetime.timedelta(hours=4.0)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Shanti Bhavan Orphanage",
            quantity_kg=45.0,
            remaining_kg=45.0,
            lat=12.9856,
            lng=77.6080,  # Frazer Town
            delivery_window_start="13:00",
            delivery_window_end="16:00",
            need_level=5,  # HIGHEST NEED
            status="open",
            created_at=now - datetime.timedelta(hours=3.5)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="St. Jude Child Care Center",
            quantity_kg=35.0,
            remaining_kg=35.0,
            lat=12.9538,
            lng=77.5833,  # Lalbagh West
            delivery_window_start="12:30",
            delivery_window_end="15:30",
            need_level=4,
            status="open",
            created_at=now - datetime.timedelta(hours=2.0)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Samarthanam Disabled Trust",
            quantity_kg=70.0,
            remaining_kg=70.0,
            lat=12.9128,
            lng=77.6445,  # HSR Sector 2
            delivery_window_start="14:30",
            delivery_window_end="18:00",
            need_level=4,
            status="open",
            created_at=now - datetime.timedelta(hours=1.5)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Vidyaranya Old Age Home",
            quantity_kg=30.0,
            remaining_kg=30.0,
            lat=13.0125,
            lng=77.5540,  # Rajajinagar
            delivery_window_start="13:00",
            delivery_window_end="16:30",
            need_level=4,
            status="open",
            created_at=now - datetime.timedelta(hours=5.0)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Karunashraya Hospice Care",
            quantity_kg=50.0,
            remaining_kg=50.0,
            lat=12.9582,
            lng=77.7125,  # Marathahalli
            delivery_window_start="15:00",
            delivery_window_end="18:30",
            need_level=5,  # HIGHEST NEED
            status="open",
            created_at=now - datetime.timedelta(hours=2.5)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Sneha Care Children Home",
            quantity_kg=40.0,
            remaining_kg=40.0,
            lat=12.8712,
            lng=77.6521,  # Begur
            delivery_window_start="14:00",
            delivery_window_end="17:30",
            need_level=3,
            status="open",
            created_at=now - datetime.timedelta(hours=1.0)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Robin Hood Army Bangalore Hub",
            quantity_kg=85.0,
            remaining_kg=85.0,
            lat=12.9730,
            lng=77.6150,  # Ulsoor
            delivery_window_start="14:00",
            delivery_window_end="19:00",
            need_level=3,
            status="open",
            created_at=now - datetime.timedelta(hours=3.0)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Ashraya Women Shelter",
            quantity_kg=25.0,
            remaining_kg=25.0,
            lat=13.0035,
            lng=77.6189,  # Cooke Town
            delivery_window_start="13:30",
            delivery_window_end="16:30",
            need_level=4,
            status="open",
            created_at=now - datetime.timedelta(hours=2.0)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Aasra Destitute Foundation",
            quantity_kg=55.0,
            remaining_kg=55.0,
            lat=12.9220,
            lng=77.5620,  # Banashankari
            delivery_window_start="15:00",
            delivery_window_end="18:00",
            need_level=3,
            status="open",
            created_at=now - datetime.timedelta(hours=1.0)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Nightingales Elders Day Centre",
            quantity_kg=20.0,
            remaining_kg=20.0,
            lat=12.9820,
            lng=77.5850,  # Vasanth Nagar
            delivery_window_start="12:00",
            delivery_window_end="15:00",
            need_level=3,
            status="open",
            created_at=now - datetime.timedelta(hours=1.5)
        ),
        Request(
            receiver_id=receiver_user.id,
            receiver_name="Community Food Bank Whitefield",
            quantity_kg=100.0,
            remaining_kg=100.0,
            lat=12.9710,
            lng=77.7500,  # Kadugodi
            delivery_window_start="10:00",
            delivery_window_end="20:00",
            need_level=2,
            status="open",
            created_at=now - datetime.timedelta(hours=6.0)
        )
    ]
    db.add_all(requests)
    db.commit()

    print("[Seed] Successfully seeded:")
    print(f"  - {db.query(User).count()} Users")
    print(f"  - {db.query(Depot).count()} Depots")
    print(f"  - {db.query(Vehicle).count()} Vehicles")
    print(f"  - {db.query(Donation).count()} Donations")
    print(f"  - {db.query(Request).count()} Requests")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_database(db, reset=True)
    finally:
        db.close()
