from flask import Blueprint, request, jsonify, g
from ..models import db, Ride, RideRequest
from ..auth.utils import token_required
from datetime import datetime
from sqlalchemy import and_

rider_bp = Blueprint("rider", __name__, url_prefix="/rider")

# GET /rider/my_rides — only accepted ride requests
@rider_bp.route("/my_pending_rides", methods=["GET"])
@token_required
def my_pending_rides():
    profile = g.current_user.profile

    accepted_requests = RideRequest.query.filter(
    and_(
        RideRequest.rider_id == profile.id,
        RideRequest.status == "accepted",
        Ride.departure_time > datetime.utcnow()  # ride hasn't happened yet
    )
    ).join(Ride).all()

    rides = []
    for req in accepted_requests:
        ride = req.ride
        rides.append({
            "ride_id": ride.id,
            "start_location": ride.start_location,
            "end_location": ride.end_location,
            "departure_time": ride.departure_time.isoformat(),
            "price_per_seat": float(ride.price_per_seat),
            "status": ride.status,
            "driver": {
                "name": ride.driver_profile.name,
                "phone": ride.driver_profile.phone,
                "photo": ride.driver_profile.photo
            }
        })

    return jsonify({"rides": rides})


# GET /rider/ride_requests — pending/non-accepted requests
@rider_bp.route("/ride_requests", methods=["GET"])
@token_required
def my_ride_requests():
    profile = g.current_user.profile

    pending_requests = RideRequest.query.filter(
        RideRequest.rider_id == profile.id,
        RideRequest.status != "accepted"
    ).all()

    requests = []
    for req in pending_requests:
        ride = req.ride
        requests.append({
            "request_id": req.id,
            "ride_id": ride.id,
            "start_location": ride.start_location,
            "end_location": ride.end_location,
            "departure_time": ride.departure_time.isoformat(),
            "status": req.status,
            "driver_name": ride.driver_profile.name
        })

    return jsonify({"requests": requests})

# POST /rider/request_ride — create a new ride request
@rider_bp.route("/request_ride", methods=["POST"])
@token_required
def send_ride_request():
    data = request.get_json()
    profile = g.current_user.profile

    ride_id = data.get("ride_id")
    message = data.get("message", "")

    ride = Ride.query.get(ride_id)
    if not ride:
        return jsonify({"error": "Ride not found"}), 404

    # Prevent duplicates
    existing = RideRequest.query.filter_by(rider_id=profile.id, ride_id=ride.id).first()
    if existing:
        return jsonify({"error": "You have already requested this ride"}), 409

    request_obj = RideRequest(
        rider_id=profile.id,
        ride_id=ride.id,
        message=message,
        status="pending"
    )

    db.session.add(request_obj)
    db.session.commit()

    return jsonify({"message": "Ride request sent", "request_id": request_obj.id})