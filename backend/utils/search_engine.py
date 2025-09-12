"""
Advanced search engine with relevance scoring and ranking algorithms
"""

from datetime import datetime
from .geospatial import haversine_distance


def calculate_ride_relevance(ride, search_params):
    """Calculate multi-factor relevance score for a ride"""
    score = 0.0
    weights = search_params.get('weights', {
        'popularity': 0.3,
        'distance': 0.25,
        'driver_rating': 0.2,
        'price': 0.15,
        'recency': 0.1
    })
    
    # Popularity score (0-100 normalized)
    popularity_score = min(ride.popularity_score / 100.0, 1.0) * 100
    score += popularity_score * weights['popularity']
    
    # Distance score (closer is better, 0-100)
    if search_params.get('from_lat') and search_params.get('from_lng'):
        distance = haversine_distance(
            search_params['from_lat'], search_params['from_lng'],
            ride.start_lat, ride.start_lng
        )
        # Convert distance to score (0-50km range, inverse scoring)
        distance_score = max(0, 100 - (distance * 2))  # 50km = 0 points
        score += distance_score * weights['distance']
    
    # Driver rating score (0-100)
    if ride.driver_profile and ride.driver_profile.driver_rating:
        rating_score = (ride.driver_profile.driver_rating / 5.0) * 100
        experience_bonus = min(ride.driver_profile.total_rides * 2, 20)
        score += (rating_score + experience_bonus) * weights['driver_rating']
    
    # Price score (lower price = higher score, 0-100)
    if search_params.get('max_price'):
        price_ratio = float(ride.price_per_seat) / search_params['max_price']
        price_score = max(0, 100 - (price_ratio * 50))
        score += price_score * weights['price']
    
    # Recency score (sooner departure = higher score, 0-100)
    if ride.departure_time > datetime.utcnow():
        hours_until = (ride.departure_time - datetime.utcnow()).total_seconds() / 3600
        if hours_until <= 24:
            recency_score = 100 - (hours_until * 2)  # 24h = 52 points, 1h = 98 points
        else:
            recency_score = max(0, 50 - (hours_until - 24) / 24 * 10)  # Gradual decline
        score += max(0, recency_score) * weights['recency']
    
    return round(score, 2)




def sort_rides_by_criteria(rides_with_scores, sort_by, search_params=None):
    """Sort rides based on specified criteria"""
    if sort_by == 'relevance':
        return sorted(rides_with_scores, key=lambda x: x['relevance_score'], reverse=True)
    elif sort_by == 'distance' and search_params and search_params.get('from_lat'):
        return sorted(rides_with_scores, key=lambda x: x.get('distance', float('inf')))
    elif sort_by == 'price':
        return sorted(rides_with_scores, key=lambda x: float(x['ride'].price_per_seat))
    elif sort_by == 'departure_time':
        return sorted(rides_with_scores, key=lambda x: x['ride'].departure_time)
    elif sort_by == 'popularity':
        return sorted(rides_with_scores, key=lambda x: x['ride'].popularity_score, reverse=True)
    elif sort_by == 'driver_rating':
        return sorted(rides_with_scores, 
                     key=lambda x: x['ride'].driver_profile.driver_rating if x['ride'].driver_profile else 0, 
                     reverse=True)
    else:
        # Default to relevance
        return sorted(rides_with_scores, key=lambda x: x['relevance_score'], reverse=True)


def calculate_search_quality_score(search_params, results_count):
    """Calculate a quality score for the search results"""
    quality_score = 0.0
    
    # Base score for having results
    if results_count > 0:
        quality_score += 50.0
    
    # Bonus for having coordinates (enables distance-based features)
    if search_params.get('from_lat') and search_params.get('from_lng'):
        quality_score += 20.0
    
    # Bonus for reasonable result count (not too few, not too many)
    if 5 <= results_count <= 25:
        quality_score += 20.0
    elif results_count > 25:
        quality_score += 10.0
    
    # Penalty for very few results
    if results_count < 3:
        quality_score -= 15.0
    
    return min(100.0, max(0.0, quality_score))


def build_search_suggestions(search_params, results_count):
    """Generate search suggestions based on search performance"""
    suggestions = []
    
    if results_count == 0:
        suggestions.append({
            'type': 'no_results',
            'message': 'No rides found. Try expanding your search distance or adjusting your filters.',
            'action': 'increase_radius'
        })
    elif results_count < 3:
        suggestions.append({
            'type': 'few_results', 
            'message': 'Limited results found. Consider expanding your search criteria.',
            'action': 'relax_filters'
        })
    
    if search_params.get('max_distance', 50) < 25:
        suggestions.append({
            'type': 'distance_suggestion',
            'message': 'Try increasing your search distance to find more rides.',
            'action': 'increase_distance'
        })
    
    if not search_params.get('from_lat') or not search_params.get('from_lng'):
        suggestions.append({
            'type': 'location_suggestion',
            'message': 'Add precise location coordinates for better distance-based results.',
            'action': 'add_coordinates'
        })
    
    return suggestions