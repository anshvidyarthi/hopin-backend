from flask import Blueprint, request, jsonify, g
from flask_cors import cross_origin
from datetime import datetime
from ..models import db, Ride, RideRequest
from ..auth.utils import token_required
from ..driver.utils import validate_ride_payload, serialize_ride_request

driver_bp = Blueprint("driver", __name__, url_prefix="/driver")

@driver_bp.route("/offer_ride", methods=["POST"])
@token_required
def offer_ride():
    data = request.get_json() or {}
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
        start_lat=data.get("start_lat"),
        start_lng=data.get("start_lng"),
        end_lat=data.get("end_lat"),
        end_lng=data.get("end_lng"),
        departure_time=datetime.fromisoformat(data["departure_time"]),
        available_seats=data["available_seats"],
        price_per_seat=data["price_per_seat"],
        pickup_flexibility=data.get("pickup_flexibility", 0),
        dropoff_flexibility=data.get("dropoff_flexibility", 0),
        is_fixed_pickup=data.get("is_fixed_pickup", False),
        fixed_pickup_location=data.get("fixed_pickup_location"),
        status=data.get("status", "available")  # let backend default if you prefer
    )

    db.session.add(ride)
    db.session.commit()

    return jsonify({"message": "Ride offered successfully", "ride_id": ride.id}), 201


@driver_bp.route("/ride/<ride_id>", methods=["PATCH"])
@token_required
def update_ride(ride_id):
    profile = g.current_user.profile

    ride = Ride.query.get(ride_id)
    if not ride:
        return jsonify({"error": "Ride not found"}), 404

    if ride.driver_id != profile.id:
        return jsonify({"error": "Unauthorized to modify this ride"}), 403

    data = request.get_json() or {}

    allowed_fields = [
        "start_location", "start_lat", "start_lng",
        "end_location", "end_lat", "end_lng",
        "departure_time", "available_seats", "price_per_seat",
        "pickup_flexibility", "dropoff_flexibility",
        "is_fixed_pickup", "fixed_pickup_location", "status"
    ]

    for field in allowed_fields:
        if field in data:
            if field == "departure_time":
                setattr(ride, field, datetime.fromisoformat(data[field]))
            else:
                setattr(ride, field, data[field])

    db.session.commit()
    return jsonify({"message": "Ride updated successfully"})

@driver_bp.route("/my_scheduled_rides", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
@token_required
def my_rides():
    profile = g.current_user.profile

    if not profile.is_driver:
        return jsonify({"error": "Only drivers can view their rides"}), 403

    rides = (
        Ride.query.filter_by(driver_id=profile.id)
        .order_by(Ride.created_at.desc())
        .all()
    )

    ride_list = []
    for ride in rides:
        ride_dict = {
            "id": ride.id,
            "start_location": ride.start_location,
            "start_lat": ride.start_lat,
            "start_lng": ride.start_lng,
            "end_location": ride.end_location,
            "end_lat": ride.end_lat,
            "end_lng": ride.end_lng,
            "departure_time": ride.departure_time.isoformat(),
            "available_seats": ride.available_seats,
            "price_per_seat": float(ride.price_per_seat),
            "status": ride.status,
            "requests": [serialize_ride_request(req) for req in ride.ride_requests],
        }
        ride_list.append(ride_dict)

    return jsonify({"rides": ride_list})

@driver_bp.route("/ride_request/<request_id>/accept", methods=["POST"])
@token_required
def accept_ride_request(request_id):
    profile = g.current_user.profile

    req = RideRequest.query.get(request_id)
    if not req:
        return jsonify({"error": "Ride request not found"}), 404

    if req.ride.driver_id != profile.id:
        return jsonify({"error": "Unauthorized to modify this request"}), 403

    if req.status != "pending":
        return jsonify({"error": f"Cannot accept a request in '{req.status}' state"}), 400

    req.status = "accepted"
    db.session.commit()
    return jsonify({"message": "Ride request accepted"})


@driver_bp.route("/ride_request/<request_id>/reject", methods=["POST"])
@token_required
def reject_ride_request(request_id):
    profile = g.current_user.profile

    req = RideRequest.query.get(request_id)
    if not req:
        return jsonify({"error": "Ride request not found"}), 404

    if req.ride.driver_id != profile.id:
        return jsonify({"error": "Unauthorized to modify this request"}), 403

    if req.status != "pending":
        return jsonify({"error": f"Cannot reject a request in '{req.status}' state"}), 400

    req.status = "rejected"
    db.session.commit()
    return jsonify({"message": "Ride request rejected"})