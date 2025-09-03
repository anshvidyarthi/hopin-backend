# Backend Utils Documentation

This directory contains utility modules to keep the codebase organized and maintainable.

## Module Structure

### `geospatial.py`
**Geospatial calculations and location processing**
- `haversine_distance(lat1, lon1, lat2, lon2)` - Calculate distance between coordinates
- `calculate_bounding_box(lat, lng, radius_km)` - Get bounding box for radius searches
- `is_within_radius(center_lat, center_lng, point_lat, point_lng, radius_km)` - Check if point is within radius

### `location_resolver.py` 
**Location alias resolution and smart matching**
- `resolve_location_aliases(location_text)` - Resolve aliases to canonical names
- `find_similar_locations(location_text, limit=5)` - Find similar location matches
- `normalize_location_name(location_text)` - Normalize location text for consistency
- `extract_location_keywords(location_text)` - Extract searchable keywords

### `search_engine.py`
**Advanced search algorithms and relevance scoring**
- `calculate_ride_relevance(ride, search_params)` - Multi-factor relevance scoring
- `calculate_popularity_boost(ride)` - Calculate popularity-based score boost
- `sort_rides_by_criteria(rides_with_scores, sort_by, search_params)` - Sort results by criteria
- `build_search_suggestions(search_params, results_count)` - Generate search improvement suggestions

### `analytics.py`
**Search analytics and user behavior tracking**
- `log_search_analytics(user_id, search_params, results_count)` - Log search for analytics
- `calculate_route_popularity_score(popular_route)` - Calculate route popularity
- `get_user_search_patterns(user_id, limit=10)` - Get user search history patterns
- `get_trending_routes(limit=10, days=7)` - Get trending routes
- `update_route_ride_stats(from_location, to_location, price_per_seat)` - Update route statistics

### `serializers.py`
**Data serialization for consistent API responses**
- `serialize_point(use_driver, loc, lat, lng)` - Serialize location point data
- `serialize_search_ride(ride, me_profile_id, search_params)` - Serialize ride data for search
- `serialize_ride_request(request, include_ride_details)` - Serialize ride request data
- `serialize_search_response(rides, search_params, location_resolution, search_quality)` - Complete search response

## Usage Example

```python
from ..utils.geospatial import haversine_distance
from ..utils.location_resolver import resolve_location_aliases
from ..utils.search_engine import calculate_ride_relevance
from ..utils.analytics import log_search_analytics
from ..utils.serializers import serialize_search_ride

# Calculate distance
distance = haversine_distance(34.0522, -118.2437, 34.0699, -118.4438)

# Resolve location aliases
resolved = resolve_location_aliases("UCLA")

# Calculate relevance score
score = calculate_ride_relevance(ride, search_params)

# Log analytics
log_search_analytics(user_id, search_params, results_count)

# Serialize response
serialized = serialize_search_ride(ride, user_id, search_params)
```

## Benefits

- **Separation of Concerns**: Business logic separated from endpoint handlers
- **Reusability**: Functions can be used across multiple modules
- **Testability**: Easy to unit test individual utility functions
- **Maintainability**: Organized code structure for easier maintenance
- **Scalability**: Easy to extend and add new functionality