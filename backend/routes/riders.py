from flask import Blueprint, request, jsonify, g
from datetime import datetime
from sqlalchemy import and_
from ..models import db, Ride, RideRequest, Message
from ..auth.utils import token_required

rider_bp = Blueprint("rider", __name__, url_prefix="/rider")


def serialize_point(use_driver: bool, loc, lat, lng):
    return {
        "use_driver": use_driver,
        "location": loc,
        "lat": lat,
        "lng": lng,
    }


def serialize_search_ride(ride: Ride, me_profile_id: str):
    """Return a ride row plus info for UX locking."""
    my_req = RideRequest.query.filter_by(rider_id=me_profile_id, ride_id=ride.id).first()
    my_status = my_req.status if my_req else None

    is_own = ride.driver_id == me_profile_id

    return {
        "ride_id": ride.id,
        "start_location": ride.start_location,
        "end_location": ride.end_location,
        "departure_time": ride.departure_time.isoformat(),
        "available_seats": ride.available_seats,
        "price_per_seat": float(ride.price_per_seat),
        "status": ride.status,
        "driver": {
            "id": ride.driver_profile.id,
            "name": ride.driver_profile.name,
            "photo": ride.driver_profile.photo,
            "rating": ride.driver_profile.rating,
            "total_rides": ride.driver_profile.total_rides,
        },
        "driver_id": ride.driver_id,
        "my_request_status": my_status,  # null | pending | accepted | rejected | declined
        "is_own_ride": is_own,
        "can_request": (not is_own) and (my_status is None) and ride.available_seats > 0 and ride.status not in ("full",),
    }


@rider_bp.route("/search_rides", methods=["GET"])
@token_required
def search_rides():
    profile = g.current_user
    start = request.args.get("from")
    end = request.args.get("to")

    if not start or not end:
        return jsonify({"error": "Both 'from' and 'to' parameters are required"}), 400

    rides = (
        Ride.query.filter(
            and_(
                Ride.departure_time > datetime.utcnow(),
                Ride.start_location.ilike(f"%{start}%"),
                Ride.end_location.ilike(f"%{end}%"),
                Ride.status.in_(["available", "scheduled"]),
            )
        )
        .order_by(Ride.departure_time.asc())
        .all()
    )

    results = [serialize_search_ride(r, profile.id) for r in rides]
    return jsonify({"rides": results})


@rider_bp.route("/my_pending_rides", methods=["GET"])
@token_required
def my_pending_rides():
    profile = g.current_user

    accepted_requests = (
        RideRequest.query.join(Ride)
        .filter(
            RideRequest.rider_id == profile.id,
            RideRequest.status == "accepted",
            Ride.departure_time > datetime.utcnow(),
        )
        .all()
    )

    rides = []
    for req in accepted_requests:
        ride = req.ride
        rides.append(
            {
                "ride_id": ride.id,
                "start_location": ride.start_location,
                "end_location": ride.end_location,
                "departure_time": ride.departure_time.isoformat(),
                "price_per_seat": float(ride.price_per_seat),
                "status": ride.status,
                "driver": {
                    "name": ride.driver_profile.name,
                    "phone": ride.driver_profile.phone,
                    "photo": ride.driver_profile.photo,
                },
                "pickup": serialize_point(
                    req.use_driver_pickup,
                    req.rider_pickup_location,
                    req.rider_pickup_lat,
                    req.rider_pickup_lng,
                ),
                "dropoff": serialize_point(
                    req.use_driver_dropoff,
                    req.rider_dropoff_location,
                    req.rider_dropoff_lat,
                    req.rider_dropoff_lng,
                ),
            }
        )

    return jsonify({"rides": rides})


@rider_bp.route("/ride_requests", methods=["GET"])
@token_required
def my_ride_requests():
    profile = g.current_user

    pending_requests = RideRequest.query.filter(
        RideRequest.rider_id == profile.id,
    ).all()

    requests = []
    for req in pending_requests:
        ride = req.ride
        requests.append(
            {
                "request_id": req.id,
                "ride_id": ride.id,
                "start_location": ride.start_location,
                "end_location": ride.end_location,
                "departure_time": ride.departure_time.isoformat(),
                "status": req.status,
                "driver_name": ride.driver_profile.name,
                "pickup": serialize_point(
                    req.use_driver_pickup,
                    req.rider_pickup_location,
                    req.rider_pickup_lat,
                    req.rider_pickup_lng,
                ),
                "dropoff": serialize_point(
                    req.use_driver_dropoff,
                    req.rider_dropoff_location,
                    req.rider_dropoff_lat,
                    req.rider_dropoff_lng,
                ),
            }
        )

    return jsonify({"requests": requests})


@rider_bp.route("/request_ride", methods=["POST"])
@token_required
def send_ride_request():
    data = request.get_json() or {}
    profile = g.current_user

    ride_id = data.get("ride_id")
    if not ride_id:
        return jsonify({"error": "ride_id is required"}), 400

    ride = Ride.query.get(ride_id)
    if not ride:
        return jsonify({"error": "Ride not found"}), 404

    if ride.driver_id == profile.id:
        return jsonify({"error": "You cannot request your own ride"}), 403

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

    # Create ride request
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

    # Create initial message
    initial_msg = data.get("message", "").strip()
    if initial_msg:
        msg = Message(
            ride_id=ride.id,
            sender_id=profile.id,
            receiver_id=ride.driver_id,
            content=initial_msg
        )
        db.session.add(msg)

    db.session.commit()

    return jsonify({"message": "Ride request sent", "request_id": req.id}), 201