from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import uuid

from sqlalchemy import Boolean, text

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Relationships
    profile = db.relationship("Profile", backref="user", uselist=False, cascade="all, delete")

class Profile(db.Model):
    __tablename__ = "profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    photo = db.Column(db.Text, nullable=True)
    driver_rating = db.Column(db.Float, default=0.0)
    rider_rating = db.Column(db.Float, default=0.0)
    total_rides = db.Column(db.Integer, default=0)
    phone = db.Column(db.String(20), nullable=True)
    is_onboarded = db.Column(Boolean, nullable=False, default=False)
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
    
    # Search optimization fields
    popularity_score = db.Column(db.Float, default=0.0)
    search_vector = db.Column(db.Text, nullable=True)  # For full-text search
    
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
    use_driver_pickup = db.Column(db.Boolean, default=True)
    use_driver_dropoff = db.Column(db.Boolean, default=True)
    rider_pickup_location = db.Column(db.String(255), nullable=True)
    rider_pickup_lat = db.Column(db.Float, nullable=True)
    rider_pickup_lng = db.Column(db.Float, nullable=True)
    rider_dropoff_location = db.Column(db.String(255), nullable=True)
    rider_dropoff_lat = db.Column(db.Float, nullable=True)
    rider_dropoff_lng = db.Column(db.Float, nullable=True)
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

class License(db.Model):
    __tablename__ = "licenses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=False, unique=True)
    document_url = db.Column(db.String(512), nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    license_number = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="PENDING") # PENDING, VERIFIED, EXPIRED, REVOKED
    expiration_date = db.Column(db.DateTime, nullable=True)
    validated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = db.relationship("Profile", backref="license", uselist=False)

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=False)
    
    # Notification metadata
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    
    # Related entity IDs for navigation
    ride_id = db.Column(db.String(36), db.ForeignKey("rides.id"), nullable=True)
    request_id = db.Column(db.String(36), db.ForeignKey("ride_requests.id"), nullable=True)
    message_id = db.Column(db.String(36), db.ForeignKey("messages.id"), nullable=True)
    other_user_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=True)
    
    # Action/navigation data as JSON
    action_data = db.Column(db.JSON, nullable=True)
    
    # Status tracking
    read = db.Column(db.Boolean, default=False)
    delivered = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship("Profile", foreign_keys=[user_id], backref="notifications")
    ride = db.relationship("Ride", foreign_keys=[ride_id])
    request = db.relationship("RideRequest", foreign_keys=[request_id])
    message = db.relationship("Message", foreign_keys=[message_id])
    other_user = db.relationship("Profile", foreign_keys=[other_user_id])

class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reviewer_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=False)
    reviewee_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=False)
    ride_id = db.Column(db.String(36), db.ForeignKey("rides.id"), nullable=True)

    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    role = db.Column(db.String(10), nullable=False)  # "driver" or "rider"

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reviewer = db.relationship("Profile", foreign_keys=[reviewer_id], backref="written_reviews")
    reviewee = db.relationship("Profile", foreign_keys=[reviewee_id], backref="received_reviews")
    ride = db.relationship("Ride", backref="reviews")

class LocationAlias(db.Model):
    __tablename__ = "location_aliases"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_name = db.Column(db.String(255), nullable=False)
    alias_name = db.Column(db.String(255), nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    popularity = db.Column(db.Integer, default=0)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SearchHistory(db.Model):
    __tablename__ = "search_history"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("profiles.id"), nullable=True)
    from_location = db.Column(db.String(255), nullable=False)
    to_location = db.Column(db.String(255), nullable=False)
    from_lat = db.Column(db.Float, nullable=True)
    from_lng = db.Column(db.Float, nullable=True)
    to_lat = db.Column(db.Float, nullable=True)
    to_lng = db.Column(db.Float, nullable=True)
    search_count = db.Column(db.Integer, default=1)
    results_count = db.Column(db.Integer, default=0)
    last_searched = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    user = db.relationship("Profile", backref="search_history")

class PopularRoute(db.Model):
    __tablename__ = "popular_routes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_location = db.Column(db.String(255), nullable=False)
    to_location = db.Column(db.String(255), nullable=False)
    from_lat = db.Column(db.Float, nullable=True)
    from_lng = db.Column(db.Float, nullable=True)
    to_lat = db.Column(db.Float, nullable=True)
    to_lng = db.Column(db.Float, nullable=True)
    search_count = db.Column(db.Integer, default=1)
    ride_count = db.Column(db.Integer, default=0)
    avg_price = db.Column(db.Numeric, nullable=True)
    popularity_score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)