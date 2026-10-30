import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="donor")  # "donor", "receiver", "admin"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    donations = relationship("Donation", back_populates="donor")
    requests = relationship("Request", back_populates="receiver")


class Depot(Base):
    __tablename__ = "depots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    vehicles = relationship("Vehicle", back_populates="depot", cascade="all, delete-orphan")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    depot_id = Column(Integer, ForeignKey("depots.id"), nullable=False)
    capacity_kg = Column(Float, nullable=False)
    available_from = Column(String(10), nullable=False, default="09:00")
    available_to = Column(String(10), nullable=False, default="21:00")
    is_active = Column(Boolean, default=True)

    depot = relationship("Depot", back_populates="vehicles")


class Donation(Base):
    __tablename__ = "donations"

    id = Column(Integer, primary_key=True, index=True)
    donor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    donor_name = Column(String(100), nullable=False)
    food_type = Column(String(100), nullable=False)
    quantity_kg = Column(Float, nullable=False)
    remaining_kg = Column(Float, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    ready_time = Column(DateTime, nullable=False)
    expiry_time = Column(DateTime, nullable=False)
    pickup_window_start = Column(String(10), nullable=False, default="12:00")
    pickup_window_end = Column(String(10), nullable=False, default="18:00")
    status = Column(String(30), nullable=False, default="open")  # open, partially_matched, matched, expired, cancelled
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    donor = relationship("User", back_populates="donations")
    matches = relationship("MatchRecord", back_populates="donation")


class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    receiver_name = Column(String(100), nullable=False)
    quantity_kg = Column(Float, nullable=False)
    remaining_kg = Column(Float, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    delivery_window_start = Column(String(10), nullable=False, default="12:00")
    delivery_window_end = Column(String(10), nullable=False, default="18:00")
    need_level = Column(Integer, nullable=False, default=3)  # 1 (lowest) to 5 (highest)
    status = Column(String(30), nullable=False, default="open")  # open, partially_matched, matched, cancelled
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    receiver = relationship("User", back_populates="requests")
    matches = relationship("MatchRecord", back_populates="request")


class MatchRecord(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, index=True, nullable=False)
    batch_id = Column(String(50), index=True, nullable=False)
    donation_id = Column(Integer, ForeignKey("donations.id"), nullable=False)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False)
    allocated_kg = Column(Float, nullable=False)
    priority_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    donation = relationship("Donation", back_populates="matches")
    request = relationship("Request", back_populates="matches")


class UnmatchedRecord(Base):
    __tablename__ = "unmatched_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(50), index=True, nullable=False)
    item_type = Column(String(20), nullable=False)  # "donation" or "request"
    item_id = Column(Integer, nullable=False)
    item_name = Column(String(100), nullable=False)
    unallocated_kg = Column(Float, nullable=False)
    reason = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
