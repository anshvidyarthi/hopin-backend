from flask import Blueprint, request, jsonify, g
from ..models import db, Ride, RideRequest
from ..auth.utils import token_required
from datetime import datetime
from sqlalchemy import and_

rider_bp = Blueprint("rider", __name__, url_prefix="/rider")

@rider_bp.route("/search_rides", methods=["GET"])
@token_required
def search_rides():
    _ = g.current_user.profile
    start = request.args.get("from")
    end = request.args.get("to")

    if not start or not end:
        return jsonify({"error": "Both 'from' and 'to' parameters are required"}), 400

    rides = Ride.query.filter(
        and_(
            Ride.status == "scheduled",
            Ride.departure_time > datetime.utcnow(),
            Ride.start_location.ilike(f"%{start}%"),
            Ride.end_location.ilike(f"%{end}%")
        )
    ).order_by(Ride.departure_time.asc()).all()

    results = []
    for ride in rides:
        results.append({
            "ride_id": ride.id,
            "start_location": ride.start_location,
            "end_location": ride.end_location,
            "departure_time": ride.departure_time.isoformat(),
            "available_seats": ride.available_seats,
            "price_per_seat": float(ride.price_per_seat),
            "driver": {
                "name": ride.driver_profile.name,
                "photo": ride.driver_profile.photo,
                "rating": ride.driver_profile.rating
            }
        })

    return jsonify({"rides": results})

@rider_bp.route("/my_pending_rides", methods=["GET"])
@token_required
def my_pending_rides():
    profile = g.current_user.profile

    accepted_requests = (
        RideRequest.query
        .join(Ride)
        .filter(
            RideRequest.rider_id == profile.id,
            RideRequest.status == "accepted",
            Ride.departure_time > datetime.utcnow()
        )
        .all()
    )

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
            },
            "pickup": {
                "use_driver": req.use_driver_pickup,
                "location": req.rider_pickup_location,
                "lat": req.rider_pickup_lat,
                "lng": req.rider_pickup_lng,
            },
            "dropoff": {
                "use_driver": req.use_driver_dropoff,
                "location": req.rider_dropoff_location,
                "lat": req.rider_dropoff_lat,
                "lng": req.rider_dropoff_lng,
            },
        })

    return jsonify({"rides": rides})


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
            "driver_name": ride.driver_profile.name,
            "pickup": {
                "use_driver": req.use_driver_pickup,
                "location": req.rider_pickup_location,
                "lat": req.rider_pickup_lat,
                "lng": req.rider_pickup_lng,
            },
            "dropoff": {
                "use_driver": req.use_driver_dropoff,
                "location": req.rider_dropoff_location,
                "lat": req.rider_dropoff_lat,
                "lng": req.rider_dropoff_lng,
            },
        })

    return jsonify({"requests": requests})


@rider_bp.route("/request_ride", methods=["POST"])
@token_required
def send_ride_request():
    data = request.get_json() or {}
    profile = g.current_user.profile

    ride_id = data.get("ride_id")
    if not ride_id:
        return jsonify({"error": "ride_id is required"}), 400

    ride = Ride.query.get(ride_id)
    if not ride:
        return jsonify({"error": "Ride not found"}), 404

    existing = RideRequest.query.filter_by(rider_id=profile.id, ride_id=ride.id).first()
    if existing:
        return jsonify({"error": "You have already requested this ride"}), 409

    use_driver_pickup = data.get("use_driver_pickup", True)
    use_driver_dropoff = data.get("use_driver_dropoff", True)

    def point(prefix: str):
        return (
            data.get(f"{prefix}_location"),
            data.get(f"{prefix}_lat"),
            data.get(f"{prefix}_lng"),
        )

    rider_pick_loc, rider_pick_lat, rider_pick_lng = point("rider_pickup")
    rider_drop_loc, rider_drop_lat, rider_drop_lng = point("rider_dropoff")

    if use_driver_pickup and not rider_pick_loc:
        rider_pick_loc = ride.start_location
        rider_pick_lat = ride.start_lat
        rider_pick_lng = ride.start_lng

    if use_driver_dropoff and not rider_drop_loc:
        rider_drop_loc = ride.end_location
        rider_drop_lat = ride.end_lat
        rider_drop_lng = ride.end_lng

    if not use_driver_pickup and not rider_pick_loc:
        return jsonify({"error": "rider_pickup_location required if not using driver pickup"}), 400
    if not use_driver_dropoff and not rider_drop_loc:
        return jsonify({"error": "rider_dropoff_location required if not using driver dropoff"}), 400

    req = RideRequest(
        rider_id=profile.id,
        ride_id=ride.id,
        message=data.get("message", ""),
        status="pending",
        use_driver_pickup=use_driver_pickup,
        use_driver_dropoff=use_driver_dropoff,
        rider_pickup_location=rider_pick_loc,
        rider_pickup_lat=rider_pick_lat,
        rider_pickup_lng=rider_pick_lng,
        rider_dropoff_location=rider_drop_loc,
        rider_dropoff_lat=rider_drop_lat,
        rider_dropoff_lng=rider_drop_lng,
    )

    db.session.add(req)
    db.session.commit()

    return jsonify({"message": "Ride request sent", "request_id": req.id}), 201