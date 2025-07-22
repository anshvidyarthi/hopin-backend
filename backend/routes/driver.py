from flask import Blueprint, request, jsonify, g
from ..models import db, Ride
from ..auth.utils import token_required
from ..driver.utils import validate_ride_payload, serialize_ride_request
from datetime import datetime

driver_bp = Blueprint('driver', __name__, url_prefix='/driver')

@driver_bp.route("/offer_ride", methods=["POST"])
@token_required
def offer_ride():
    data = request.get_json()
    profile = g.current_user.profile

    if not profile.is_driver:
        return jsonify({"error": "Only drivers can offer rides"}), 403

    valid, error = validate_ride_payload(data)
    if not valid:
        return jsonify({"error": error}), 400

    ride = Ride(
        driver_id=profile.id,
        start_location=data["start_location"],
        end_location=data["end_location"],
        departure_time=datetime.fromisoformat(data["departure_time"]),
        available_seats=data["available_seats"],
        price_per_seat=data["price_per_seat"],
        pickup_flexibility=data.get("pickup_flexibility", 0),
        dropoff_flexibility=data.get("dropoff_flexibility", 0),
        is_fixed_pickup=data.get("is_fixed_pickup", False),
        fixed_pickup_location=data.get("fixed_pickup_location")
    )

    db.session.add(ride)
    db.session.commit()

    return jsonify({"message": "Ride offered successfully", "ride_id": ride.id})

@driver_bp.route("/my_rides", methods=["GET"])
@token_required
def my_rides():
    profile = g.current_user.profile

    if not profile.is_driver:
        return jsonify({"error": "Only drivers can view their rides"}), 403

    rides = Ride.query.filter_by(driver_id=profile.id).order_by(Ride.created_at.desc()).all()

    ride_list = []
    for ride in rides:
        ride_dict = {
            "id": ride.id,
            "start_location": ride.start_location,
            "end_location": ride.end_location,
            "departure_time": ride.departure_time.isoformat(),
            "available_seats": ride.available_seats,
            "price_per_seat": float(ride.price_per_seat),
            "status": ride.status,
            "requests": [serialize_ride_request(req) for req in ride.ride_requests]
        }
        ride_list.append(ride_dict)

    return jsonify({"rides": ride_list})