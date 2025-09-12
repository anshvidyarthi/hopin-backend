"""
Data serialization utilities for API responses
"""

from .geospatial import haversine_distance
from .search_engine import calculate_ride_relevance


def serialize_point(use_driver: bool, loc, lat, lng):
    """Serialize location point data"""
    return {
        "use_driver": use_driver,
        "location": loc,
        "lat": lat,
        "lng": lng,
    }


def serialize_search_ride(ride, me_profile_id, search_params=None):
    """Return a ride row plus info for UX locking and search data."""
    from ..models import RideRequest
    
    my_req = RideRequest.query.filter_by(rider_id=me_profile_id, ride_id=ride.id).first()
    my_status = my_req.status if my_req else None

    is_own = ride.driver_id == me_profile_id

    # Calculate distance if coordinates available
    distance = None
    if (search_params and search_params.get('from_lat') and search_params.get('from_lng') and 
        ride.start_lat and ride.start_lng):
        distance = haversine_distance(
            search_params['from_lat'], search_params['from_lng'],
            ride.start_lat, ride.start_lng
        )

    result = {
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
            "rating": ride.driver_profile.driver_rating,
            "total_rides": ride.driver_profile.total_rides,
        },
        "driver_id": ride.driver_id,
        "my_request_status": my_status,  # null | pending | accepted | rejected | declined
        "is_own_ride": is_own,
        "can_request": (not is_own) and (my_status is None) and ride.available_seats > 0 and ride.status not in ("full",),
        
        # Enhanced search data
        "popularity_score": ride.popularity_score,
        "coordinates": {
            "start_lat": ride.start_lat,
            "start_lng": ride.start_lng,
            "end_lat": ride.end_lat,
            "end_lng": ride.end_lng
        }
    }
    
    # Add optional search-specific fields
    if search_params:
        result["relevance_score"] = calculate_ride_relevance(ride, search_params)
        if distance is not None:
            result["distance_km"] = round(distance, 1)
            result["distance_miles"] = round(distance / 1.609344, 1)  # Convert km to miles
    
    return result


def serialize_ride_request(request, include_ride_details=True):
    """Serialize ride request data"""
    data = {
        "request_id": request.id,
        "rider_id": request.rider_id,
        "ride_id": request.ride_id,
        "status": request.status,
        "message": request.message,
        "created_at": request.created_at.isoformat(),
        "pickup": serialize_point(
            request.use_driver_pickup,
            request.rider_pickup_location,
            request.rider_pickup_lat,
            request.rider_pickup_lng,
        ),
        "dropoff": serialize_point(
            request.use_driver_dropoff,
            request.rider_dropoff_location,
            request.rider_dropoff_lat,
            request.rider_dropoff_lng,
        ),
    }
    
    if include_ride_details and request.ride:
        ride = request.ride
        data["ride_details"] = {
            "start_location": ride.start_location,
            "end_location": ride.end_location,
            "departure_time": ride.departure_time.isoformat(),
            "price_per_seat": float(ride.price_per_seat) if ride.price_per_seat else 0.0,
            "available_seats": ride.available_seats or 0,
        }
        
        if ride.driver_profile:
            data["driver"] = {
                "name": ride.driver_profile.name,
                "photo": ride.driver_profile.photo,
                "rating": float(ride.driver_profile.driver_rating) if ride.driver_profile.driver_rating else 0.0,
                "total_rides": ride.driver_profile.total_rides or 0,
            }
    
    return data


def serialize_location_suggestion(location_data):
    """Serialize location data for suggestions (works with both LocationAlias objects and dicts)"""
    # Handle both LocationAlias objects and dictionary data
    if hasattr(location_data, 'canonical_name'):
        # LocationAlias object
        return {
            "canonical_name": location_data.canonical_name,
            "alias_name": location_data.alias_name,
            "display_name": location_data.canonical_name,
            "coordinates": {
                "lat": location_data.lat,
                "lng": location_data.lng
            },
            "city": location_data.city,
            "state": location_data.state,
            "popularity": location_data.popularity,
            "relevance_boost": getattr(location_data, 'relevance_boost', 0),
            "user_searched": getattr(location_data, 'user_searched', False)
        }
    else:
        # Dictionary data
        return {
            "canonical_name": location_data.get('canonical_name'),
            "alias_name": location_data.get('alias_name'),
            "display_name": location_data.get('canonical_name') or location_data.get('name'),
            "coordinates": {
                "lat": location_data.get('lat'),
                "lng": location_data.get('lng')
            },
            "city": location_data.get('city'),
            "state": location_data.get('state'),
            "popularity": location_data.get('popularity', 0),
            "relevance_boost": location_data.get('relevance_boost', 0),
            "user_searched": location_data.get('user_searched', False)
        }


def serialize_search_response(rides, search_params, location_resolution=None, search_quality=None):
    """Serialize complete search response with metadata"""
    response = {
        "rides": rides,
        "search_info": {
            "total_results": len(rides),
            "search_params": {
                "from": search_params.get('from'),
                "to": search_params.get('to'),
                "sort_by": search_params.get('sort_by', 'relevance'),
                "max_distance": search_params.get('max_distance'),
                "use_full_text": search_params.get('use_full_text', True)
            }
        }
    }
    
    # Add location resolution info if used
    if location_resolution:
        response["location_resolution"] = location_resolution
    
    # Add search quality metrics if available
    if search_quality:
        response["search_quality"] = search_quality
    
    return response