from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Relationships
    sessions = db.relationship("Session", backref="user", lazy=True, cascade="all, delete")
    profile = db.relationship("Profile", backref="user", uselist=False, cascade="all, delete")

class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    refresh_token = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=30))
    user_agent = db.Column(db.String(512))
    ip_address = db.Column(db.String(64))

class Profile(db.Model):
    __tablename__ = "profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    photo = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Float, default=0.0)
    total_rides = db.Column(db.Integer, default=0)
    is_driver = db.Column(db.Boolean, default=False)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rides = db.relationship("Ride", backref="driver_profile", foreign_keys="Ride.driver_id", cascade="all, delete")
    ride_requests = db.relationship("RideRequest", backref="rider_profile", foreign_keys="RideRequest.rider_id", cascade="all, delete")

class Ride(db.Model):
    __tablename__ = "rides"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=False)
    start_location = db.Column(db.String(255), nullable=False)
    start_lat = db.Column(db.Float, nullable=True)
    start_lng = db.Column(db.Float, nullable=True)
    end_location = db.Column(db.String(255), nullable=False)
    end_lat = db.Column(db.Float, nullable=True)
    end_lng = db.Column(db.Float, nullable=True)
    departure_time = db.Column(db.DateTime, nullable=False)
    available_seats = db.Column(db.Integer, default=1)
    price_per_seat = db.Column(db.Numeric, nullable=False)
    pickup_flexibility = db.Column(db.Integer, default=0)
    dropoff_flexibility = db.Column(db.Integer, default=0)
    is_fixed_pickup = db.Column(db.Boolean, default=False)
    fixed_pickup_location = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default="scheduled")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ride_requests = db.relationship("RideRequest", backref="ride", cascade="all, delete")
    messages = db.relationship("Message", backref="ride", cascade="all, delete")

class RideRequest(db.Model):
    __tablename__ = "ride_requests"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rider_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=False)
    ride_id = db.Column(db.String(36), db.ForeignKey("rides.id"), nullable=False)
    status = db.Column(db.String(50), default="pending")
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=False)
    receiver_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=False)
    ride_id = db.Column(db.String(36), db.ForeignKey("rides.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)