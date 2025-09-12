from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, text, func
from sqlalchemy.orm import joinedload
from ..models import db, Ride, RideRequest, Message, Profile
from ..auth.utils import token_required
from ..utils.geospatial import haversine_distance
from ..utils.location_resolver import resolve_location_aliases
from ..utils.search_engine import calculate_ride_relevance, sort_rides_by_criteria, build_search_suggestions
from ..utils.analytics import log_search_analytics
from ..utils.serializers import serialize_point, serialize_search_ride, serialize_search_response
from ..services.notifications import NotificationService

rider_bp = Blueprint("rider", __name__, url_prefix="/rider")




@rider_bp.route("/search_rides/advanced", methods=["POST"])
@token_required
def advanced_search_rides():
    """Advanced search with geospatial, relevance scoring, and analytics"""
    profile = g.current_user
    data = request.get_json() or {}
    
    # Extract search parameters
    from_location = data.get("from", "").strip()
    to_location = data.get("to", "").strip()
    
    if not from_location or not to_location:
        return jsonify({"error": "Both 'from' and 'to' parameters are required"}), 400
    
    # Search parameters with defaults
    search_params = {
        'from': from_location,
        'to': to_location,
        'from_lat': data.get('from_lat'),
        'from_lng': data.get('from_lng'),
        'to_lat': data.get('to_lat'),
        'to_lng': data.get('to_lng'),
        'date': data.get('date'),
        'max_distance': data.get('max_distance', 25),  # miles (converted from km later)
        'max_price': data.get('max_price'),
        'min_seats': data.get('min_seats', 1),
        'sort_by': data.get('sort_by', 'relevance'),  # relevance, distance, price, departure_time
        'limit': min(data.get('limit', 50), 100),  # Max 100 results
        'use_full_text': data.get('use_full_text', True),
        'resolve_aliases': data.get('resolve_aliases', True)
    }
    
    # Convert miles to km for internal calculations
    if search_params['max_distance']:
        search_params['max_distance_km'] = search_params['max_distance'] * 1.609344
    else:
        search_params['max_distance_km'] = 40.234  # 25 miles default
    
    # Resolve location aliases if enabled
    from_resolved = None
    to_resolved = None
    
    if search_params['resolve_aliases']:
        from_resolved = resolve_location_aliases(from_location)
        to_resolved = resolve_location_aliases(to_location)
        
        # Update coordinates if resolved
        if from_resolved and not search_params['from_lat']:
            search_params['from_lat'] = from_resolved['lat']
            search_params['from_lng'] = from_resolved['lng']
            
        if to_resolved and not search_params['to_lat']:
            search_params['to_lat'] = to_resolved['lat']
            search_params['to_lng'] = to_resolved['lng']
    
    # Build base filter conditions
    filter_conditions = [
        Ride.status.in_(["available", "scheduled"]),
        Ride.available_seats >= search_params['min_seats']
    ]
    
    # Time filter - only future rides (with 30-minute buffer)
    current_time = datetime.utcnow() - timedelta(minutes=30)
    filter_conditions.append(Ride.departure_time >= current_time)
    
    # Date filter if specified
    if search_params['date']:
        try:
            target_date = datetime.fromisoformat(search_params['date'].replace('Z', '+00:00'))
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            filter_conditions.append(Ride.departure_time >= start_of_day)
            filter_conditions.append(Ride.departure_time < end_of_day)
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    # Price filter
    if search_params['max_price']:
        filter_conditions.append(Ride.price_per_seat <= search_params['max_price'])
    
    # Unified location filtering strategy - works for both addresses and general areas
    location_conditions = []
    
    if search_params['use_full_text']:
        # Full-text search using PostgreSQL - handles both addresses and areas well
        location_conditions.append(
            text("to_tsvector('english', start_location) @@ plainto_tsquery('english', :from_query)")
        )
        location_conditions.append(
            text("to_tsvector('english', end_location) @@ plainto_tsquery('english', :to_query)")
        )
    else:
        # Flexible ILIKE matching - handles addresses, cities, and partial matches
        # Split location into parts for better matching
        from_parts = [from_location.strip()]
        to_parts = [to_location.strip()]
        
        # Add city part if location contains comma (like "San Luis Obispo, CA")
        if ',' in from_location:
            from_parts.append(from_location.split(',')[0].strip())
        if ',' in to_location:
            to_parts.append(to_location.split(',')[0].strip())
            
        # Create OR conditions for flexible matching
        from_conditions = [Ride.start_location.ilike(f"%{part}%") for part in from_parts]
        to_conditions = [Ride.end_location.ilike(f"%{part}%") for part in to_parts]
        
        location_conditions.extend([
            or_(*from_conditions),
            or_(*to_conditions)
        ])
    
    # Build the query
    query = Ride.query.options(joinedload(Ride.driver_profile))
    
    if search_params['use_full_text']:
        query = query.filter(
            and_(
                *filter_conditions,
                location_conditions[0],
                location_conditions[1]
            )
        ).params(from_query=from_location, to_query=to_location)
    else:
        query = query.filter(and_(*filter_conditions, *location_conditions))
    
    # Distance filtering if coordinates available
    rides = query.all()
    
    if search_params['from_lat'] and search_params['from_lng'] and search_params['max_distance_km']:
        rides = [
            ride for ride in rides 
            if ride.start_lat and ride.start_lng and 
            haversine_distance(
                search_params['from_lat'], search_params['from_lng'],
                ride.start_lat, ride.start_lng
            ) <= search_params['max_distance_km']
        ]
    
    # Calculate relevance scores and sort
    rides_with_scores = []
    for ride in rides:
        ride_data = {
            'ride': ride,
            'relevance_score': calculate_ride_relevance(ride, search_params),
            'distance': None
        }
        
        # Calculate distance if coordinates available
        if (search_params['from_lat'] and search_params['from_lng'] and 
            ride.start_lat and ride.start_lng):
            ride_data['distance'] = haversine_distance(
                search_params['from_lat'], search_params['from_lng'],
                ride.start_lat, ride.start_lng
            )
        
        rides_with_scores.append(ride_data)
    
    # Sort results using utility function
    rides_with_scores = sort_rides_by_criteria(rides_with_scores, search_params['sort_by'], search_params)
    
    # Limit results
    rides_with_scores = rides_with_scores[:search_params['limit']]
    
    # Serialize results
    results = []
    for ride_data in rides_with_scores:
        ride_result = serialize_search_ride(ride_data['ride'], profile.id, search_params)
        results.append(ride_result)
    
    # Log search analytics
    log_search_analytics(profile.id, search_params, len(results))
    
    # Build response with location resolution info
    location_resolution = None
    if search_params['resolve_aliases']:
        location_resolution = {
            "from_resolved": from_resolved,
            "to_resolved": to_resolved
        }
    
    # Generate search suggestions
    search_suggestions = build_search_suggestions(search_params, len(results))
    
    response = serialize_search_response(
        results, 
        search_params, 
        location_resolution,
        {"suggestions": search_suggestions}
    )
    
    return jsonify(response)


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

    pending_requests = RideRequest.query.options(
        joinedload(RideRequest.ride).joinedload(Ride.driver_profile)
    ).filter(
        RideRequest.rider_id == profile.id,
    ).all()

    requests = []
    for req in pending_requests:
        ride = req.ride
        
        # Handle potential None values
        price_per_seat = float(ride.price_per_seat) if ride.price_per_seat is not None else 0.0
        available_seats = ride.available_seats if ride.available_seats is not None else 0
        
        requests.append({
            "request_id": req.id,
            "ride_id": ride.id,
            "start_location": ride.start_location,
            "end_location": ride.end_location,
            "departure_time": ride.departure_time.isoformat(),
            "status": req.status,
            "driver_name": ride.driver_profile.name,
            "driver_photo": ride.driver_profile.photo if ride.driver_profile.photo else None,
            "driver_rating": float(ride.driver_profile.driver_rating) if ride.driver_profile.driver_rating is not None else 0.0,
            "driver_total_rides": ride.driver_profile.total_rides if ride.driver_profile.total_rides is not None else 0,
            "price_per_seat": price_per_seat,
            "available_seats": available_seats,
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
        })

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

    # Send initial message through WebSocket if provided
    if initial_msg:
        from backend.socket_handlers import emit_message_to_conversation
        emit_message_to_conversation(msg, ride.id, profile.id, ride.driver_id)

    # Send notification to driver
    NotificationService.ride_request_received(ride.driver_id, req, profile)

    return jsonify({"message": "Ride request sent", "request_id": req.id}), 201


@rider_bp.route("/ride/<ride_id>/details", methods=["GET"])
@token_required
def get_ride_details(ride_id):
    """Get detailed information about a specific ride"""
    profile = g.current_user
    
    # Get the ride
    ride = Ride.query.filter_by(id=ride_id).first()
    if not ride:
        return jsonify({"error": "Ride not found"}), 404
    
    # Get driver information
    driver_profile = Profile.query.filter_by(id=ride.driver_id).first()
    if not driver_profile:
        return jsonify({"error": "Driver profile not found"}), 404
    
    # Check if current user has any requests for this ride
    user_request = RideRequest.query.filter_by(
        rider_id=profile.id,
        ride_id=ride.id
    ).first()
    
    # Get user's request status
    user_request_status = user_request.status if user_request else None
    
    return jsonify({
        "ride": {
            "id": ride.id,
            "driver_id": ride.driver_id,
            "start_location": ride.start_location,
            "end_location": ride.end_location,
            "departure_time": ride.departure_time.isoformat(),
            "available_seats": ride.available_seats,
            "price_per_seat": float(ride.price_per_seat) if ride.price_per_seat else 0,
            "status": ride.status,
            "start_lat": ride.start_lat,
            "start_lng": ride.start_lng,
            "end_lat": ride.end_lat,
            "end_lng": ride.end_lng,
            "created_at": ride.created_at.isoformat(),
        },
        "driver": {
            "id": driver_profile.id,
            "name": driver_profile.name,
            "photo": driver_profile.photo,
            "rating": driver_profile.driver_rating,
            "total_rides": driver_profile.total_rides,
            "phone": driver_profile.phone if user_request_status == "accepted" else None,  # Only show phone if request accepted
        },
        "user_request": {
            "id": user_request.id if user_request else None,
            "status": user_request_status,
            "message": user_request.message if user_request else None,
            "created_at": user_request.created_at.isoformat() if user_request else None,
            "pickup": {
                "use_driver": user_request.use_driver_pickup if user_request else None,
                "location": user_request.rider_pickup_location if user_request else None,
                "lat": user_request.rider_pickup_lat if user_request else None,
                "lng": user_request.rider_pickup_lng if user_request else None,
            } if user_request else None,
            "dropoff": {
                "use_driver": user_request.use_driver_dropoff if user_request else None,
                "location": user_request.rider_dropoff_location if user_request else None,
                "lat": user_request.rider_dropoff_lat if user_request else None,
                "lng": user_request.rider_dropoff_lng if user_request else None,
            } if user_request else None,
        } if user_request else None,
    }), 200
