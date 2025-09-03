"""
Geospatial utility functions for distance calculations and location processing
"""

import math


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on Earth in kilometers"""
    if not all([lat1, lon1, lat2, lon2]):
        return float('inf')
    
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    return c * r


def degrees_to_radians(degrees):
    """Convert degrees to radians"""
    return math.radians(degrees)


def radians_to_degrees(radians):
    """Convert radians to degrees"""
    return math.degrees(radians)


def calculate_bounding_box(lat, lng, radius_km):
    """Calculate bounding box coordinates for a given center point and radius"""
    if not all([lat, lng, radius_km]):
        return None
        
    # Earth's radius in km
    earth_radius = 6371.0
    
    # Calculate latitude bounds
    lat_delta = radius_km / earth_radius
    min_lat = lat - math.degrees(lat_delta)
    max_lat = lat + math.degrees(lat_delta)
    
    # Calculate longitude bounds (varies with latitude)
    lng_delta = radius_km / (earth_radius * math.cos(math.radians(lat)))
    min_lng = lng - math.degrees(lng_delta)
    max_lng = lng + math.degrees(lng_delta)
    
    return {
        'min_lat': min_lat,
        'max_lat': max_lat,
        'min_lng': min_lng,
        'max_lng': max_lng
    }


def is_within_radius(center_lat, center_lng, point_lat, point_lng, radius_km):
    """Check if a point is within a given radius of a center point"""
    distance = haversine_distance(center_lat, center_lng, point_lat, point_lng)
    return distance <= radius_km