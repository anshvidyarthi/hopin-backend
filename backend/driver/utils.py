def validate_ride_payload(data):
    required_fields = [
        "start_location", "end_location",
        "start_lat", "start_lng", "end_lat", "end_lng",
        "departure_time", "available_seats", "price_per_seat"
    ]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return False, f"Missing fields: {', '.join(missing)}"
    return True, None

def serialize_ride_request(req):
    rider_profile = req.rider_profile
    return {
        "id": req.id,
        "status": req.status,
        "message": req.message,
        "requested_at": req.created_at.isoformat(),
        "updated_at": req.updated_at.isoformat() if req.updated_at else None,
        "rider": {
            "id": rider_profile.id,
            "name": rider_profile.name,
            "email": rider_profile.email,
            "photo": rider_profile.photo
        }
    }