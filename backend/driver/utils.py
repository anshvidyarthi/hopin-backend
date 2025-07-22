def validate_ride_payload(data):
    required_fields = ["start_location", "end_location", "departure_time", "available_seats", "price_per_seat"]
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
        "rider": {
            "id": rider_profile.id,
            "name": rider_profile.name,
            "email": rider_profile.email,
            "photo": rider_profile.photo
        }
    }