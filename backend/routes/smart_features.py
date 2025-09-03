"""
Smart Features API - Location autocomplete, recommendations, and analytics
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, text, func, desc
from ..models import db, LocationAlias, SearchHistory, PopularRoute, Ride, Profile
from ..auth.utils import token_required
from ..utils.location_resolver import find_similar_locations, normalize_location_name
from ..utils.analytics import (
    get_user_search_patterns, get_trending_routes, 
    get_search_analytics_summary, calculate_route_popularity_score
)
from ..utils.serializers import serialize_location_suggestion
from ..utils.ride_optimizer import (
    get_optimal_posting_time, analyze_route_competition, 
    get_demand_forecast, suggest_alternative_routes,
    get_optimization_recommendations
)

smart_bp = Blueprint("smart", __name__, url_prefix="/smart")


@smart_bp.route("/locations/autocomplete", methods=["GET"])
@token_required
def location_autocomplete():
    """Location autocomplete with alias suggestions"""
    query = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 10)), 20)
    
    if not query or len(query) < 2:
        return jsonify({"suggestions": []})
    
    # Get user's search history for personalization
    profile = g.current_user
    user_patterns = get_user_search_patterns(profile.id, limit=5)
    
    # Find matching locations
    suggestions = find_similar_locations(query, limit=limit)
    
    # Add user history boost to relevance
    for suggestion in suggestions:
        suggestion['relevance_boost'] = 0
        suggestion['user_searched'] = False
        
        # Check if user has searched this location before
        for pattern in user_patterns:
            if (suggestion['canonical_name'].lower() in pattern['from_location'].lower() or 
                suggestion['canonical_name'].lower() in pattern['to_location'].lower()):
                suggestion['relevance_boost'] = pattern['search_count'] * 10
                suggestion['user_searched'] = True
                break
    
    # Sort by popularity + user history boost
    suggestions.sort(key=lambda x: x['popularity'] + x['relevance_boost'], reverse=True)
    
    # Serialize suggestions
    serialized_suggestions = [serialize_location_suggestion(suggestion) for suggestion in suggestions[:limit]]
    
    return jsonify({
        "suggestions": serialized_suggestions,
        "query": query,
        "total_results": len(suggestions)
    })


@smart_bp.route("/routes/popular", methods=["GET"])
@token_required
def popular_routes():
    """Get popular routes with optional filtering"""
    limit = min(int(request.args.get("limit", 10)), 50)
    days = int(request.args.get("days", 30))
    from_location = request.args.get("from", "").strip()
    
    # Get trending routes
    trending = get_trending_routes(limit=limit * 2, days=days)  # Get more to filter
    
    # Filter by from_location if specified
    if from_location:
        trending = [
            route for route in trending 
            if from_location.lower() in route['from_location'].lower()
        ]
    
    # Limit results
    trending = trending[:limit]
    
    # Enhance with additional metrics
    enhanced_routes = []
    for route in trending:
        # Get recent rides for this route
        recent_rides = Ride.query.filter(
            and_(
                Ride.start_location.ilike(f"%{route['from_location']}%"),
                Ride.end_location.ilike(f"%{route['to_location']}%"),
                Ride.departure_time >= datetime.utcnow() - timedelta(days=days)
            )
        ).count()
        
        route_data = {
            **route,
            "recent_rides": recent_rides,
            "avg_price_formatted": f"${float(route['avg_price']):.2f}" if route['avg_price'] else "N/A",
            "trend": "up" if route['popularity_score'] > 50 else "stable"
        }
        enhanced_routes.append(route_data)
    
    return jsonify({
        "popular_routes": enhanced_routes,
        "filters": {
            "days": days,
            "from_location": from_location or None
        },
        "total_results": len(enhanced_routes)
    })


@smart_bp.route("/suggestions/personal", methods=["GET"])
@token_required
def personalized_suggestions():
    """Get personalized search suggestions based on user history"""
    profile = g.current_user
    limit = min(int(request.args.get("limit", 5)), 10)
    
    # Get user's search patterns
    patterns = get_user_search_patterns(profile.id, limit=limit)
    
    # Get trending routes that align with user preferences
    user_locations = set()
    for pattern in patterns:
        user_locations.add(pattern['from_location'].lower())
        user_locations.add(pattern['to_location'].lower())
    
    # Get trending routes
    trending = get_trending_routes(limit=20, days=14)
    
    # Find trending routes that match user's location preferences
    relevant_trends = []
    for route in trending:
        relevance_score = 0
        
        # Check if route involves user's frequent locations
        for location in user_locations:
            if (location in route['from_location'].lower() or 
                location in route['to_location'].lower()):
                relevance_score += 20
        
        if relevance_score > 0:
            route['relevance_score'] = relevance_score
            relevant_trends.append(route)
    
    # Sort by relevance and popularity
    relevant_trends.sort(key=lambda x: x['relevance_score'] + x['popularity_score'], reverse=True)
    
    suggestions = {
        "frequent_searches": [
            {
                "from_location": pattern['from_location'],
                "to_location": pattern['to_location'],
                "search_count": pattern['search_count'],
                "last_searched": pattern['last_searched'],
                "avg_results": pattern['avg_results']
            } for pattern in patterns
        ],
        "trending_for_you": relevant_trends[:limit],
        "quick_actions": []
    }
    
    # Add quick action suggestions
    if patterns:
        most_frequent = patterns[0]
        suggestions["quick_actions"].append({
            "type": "repeat_search",
            "title": f"Search {most_frequent['from_location']} to {most_frequent['to_location']} again",
            "from_location": most_frequent['from_location'],
            "to_location": most_frequent['to_location'],
            "coordinates": most_frequent['coordinates']
        })
    
    return jsonify(suggestions)


@smart_bp.route("/analytics/search", methods=["GET"])
@token_required
def search_analytics():
    """Get search analytics for the current user"""
    profile = g.current_user
    days = int(request.args.get("days", 30))
    
    # Get user analytics summary
    summary = get_search_analytics_summary(user_id=profile.id, days=days)
    
    if not summary:
        return jsonify({"error": "Unable to fetch analytics"}), 500
    
    # Get user's search patterns over time
    search_history = SearchHistory.query.filter_by(user_id=profile.id).order_by(
        SearchHistory.last_searched.desc()
    ).limit(50).all()
    
    # Aggregate by day
    daily_searches = {}
    route_frequency = {}
    
    for history in search_history:
        if history.last_searched:
            day_key = history.last_searched.strftime('%Y-%m-%d')
            daily_searches[day_key] = daily_searches.get(day_key, 0) + history.search_count
            
            route_key = f"{history.from_location} → {history.to_location}"
            route_frequency[route_key] = route_frequency.get(route_key, 0) + history.search_count
    
    # Get most productive search times
    hourly_patterns = {}
    for history in search_history:
        if history.last_searched:
            hour = history.last_searched.hour
            hourly_patterns[hour] = hourly_patterns.get(hour, 0) + history.search_count
    
    analytics_data = {
        **summary,
        "search_patterns": {
            "daily_activity": [
                {"date": date, "searches": count} 
                for date, count in sorted(daily_searches.items())
            ][-30:],  # Last 30 days
            "route_frequency": [
                {"route": route, "count": count}
                for route, count in sorted(route_frequency.items(), key=lambda x: x[1], reverse=True)
            ][:10],  # Top 10 routes
            "hourly_activity": [
                {"hour": hour, "searches": count}
                for hour, count in sorted(hourly_patterns.items())
            ]
        },
        "insights": []
    }
    
    # Generate insights
    if summary['total_searches'] > 20:
        analytics_data["insights"].append({
            "type": "power_user",
            "message": f"You're an active searcher with {summary['total_searches']} searches!",
            "icon": "⭐"
        })
    
    if summary['avg_results_per_search'] < 3:
        analytics_data["insights"].append({
            "type": "search_tip",
            "message": "Try expanding your search radius to find more ride options.",
            "icon": "💡"
        })
    
    most_common_route = max(route_frequency.items(), key=lambda x: x[1]) if route_frequency else None
    if most_common_route and most_common_route[1] >= 3:
        analytics_data["insights"].append({
            "type": "frequent_route",
            "message": f"Your most searched route is {most_common_route[0]}",
            "icon": "🛣️"
        })
    
    return jsonify(analytics_data)


@smart_bp.route("/routes/trending", methods=["GET"])
@token_required 
def trending_routes():
    """Get trending routes with advanced analytics"""
    limit = min(int(request.args.get("limit", 10)), 50)
    days = int(request.args.get("days", 7))
    include_metrics = request.args.get("include_metrics", "false").lower() == "true"
    
    # Get trending routes
    trending = get_trending_routes(limit=limit, days=days)
    
    if include_metrics:
        # Add detailed metrics for each route
        for route in trending:
            # Get ride statistics
            rides_query = Ride.query.filter(
                and_(
                    Ride.start_location.ilike(f"%{route['from_location']}%"),
                    Ride.end_location.ilike(f"%{route['to_location']}%"),
                    Ride.created_at >= datetime.utcnow() - timedelta(days=days)
                )
            )
            
            route_rides = rides_query.all()
            route['metrics'] = {
                "rides_posted": len(route_rides),
                "avg_seats": sum(ride.available_seats for ride in route_rides) / len(route_rides) if route_rides else 0,
                "price_range": {
                    "min": min(float(ride.price_per_seat) for ride in route_rides) if route_rides else 0,
                    "max": max(float(ride.price_per_seat) for ride in route_rides) if route_rides else 0
                },
                "driver_ratings": [
                    ride.driver_profile.driver_rating 
                    for ride in route_rides 
                    if ride.driver_profile and ride.driver_profile.driver_rating
                ],
                "growth_rate": calculate_growth_rate(route['from_location'], route['to_location'], days)
            }
            
            # Calculate average driver rating for this route
            ratings = route['metrics']['driver_ratings']
            route['metrics']['avg_driver_rating'] = sum(ratings) / len(ratings) if ratings else 0
    
    return jsonify({
        "trending_routes": trending,
        "period_days": days,
        "include_metrics": include_metrics,
        "total_results": len(trending)
    })


@smart_bp.route("/pricing/insights", methods=["GET"])
@token_required
def pricing_insights():
    """Get dynamic pricing insights based on route popularity"""
    from_location = request.args.get("from", "").strip()
    to_location = request.args.get("to", "").strip()
    days = int(request.args.get("days", 30))
    
    if not from_location or not to_location:
        return jsonify({"error": "Both 'from' and 'to' parameters are required"}), 400
    
    # Get route statistics
    popular_route = PopularRoute.query.filter_by(
        from_location=from_location,
        to_location=to_location
    ).first()
    
    # Get recent rides for price analysis
    recent_rides = Ride.query.filter(
        and_(
            Ride.start_location.ilike(f"%{from_location}%"),
            Ride.end_location.ilike(f"%{to_location}%"),
            Ride.departure_time >= datetime.utcnow() - timedelta(days=days),
            Ride.departure_time >= datetime.utcnow()  # Only future rides
        )
    ).all()
    
    if not recent_rides:
        return jsonify({
            "insights": {
                "message": "No recent pricing data available for this route",
                "suggestion": "This might be a good opportunity to post a ride!"
            }
        })
    
    # Calculate pricing statistics
    prices = [float(ride.price_per_seat) for ride in recent_rides]
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)
    
    # Calculate demand indicators
    total_seats_available = sum(ride.available_seats for ride in recent_rides)
    total_rides = len(recent_rides)
    avg_seats_per_ride = total_seats_available / total_rides
    
    # Get search demand
    search_demand = SearchHistory.query.filter(
        and_(
            SearchHistory.from_location.ilike(f"%{from_location}%"),
            SearchHistory.to_location.ilike(f"%{to_location}%"),
            SearchHistory.last_searched >= datetime.utcnow() - timedelta(days=days)
        )
    ).with_entities(func.sum(SearchHistory.search_count)).scalar() or 0
    
    # Calculate demand-to-supply ratio
    supply_score = total_seats_available
    demand_score = search_demand
    demand_supply_ratio = demand_score / max(supply_score, 1)
    
    insights = {
        "route": {
            "from_location": from_location,
            "to_location": to_location
        },
        "pricing": {
            "average_price": round(avg_price, 2),
            "price_range": {
                "min": min_price,
                "max": max_price
            },
            "price_distribution": calculate_price_distribution(prices),
            "recommended_price": calculate_recommended_price(avg_price, demand_supply_ratio)
        },
        "market_analysis": {
            "total_rides_posted": total_rides,
            "total_seats_available": total_seats_available,
            "search_demand": search_demand,
            "demand_supply_ratio": round(demand_supply_ratio, 2),
            "market_temperature": get_market_temperature(demand_supply_ratio),
            "avg_seats_per_ride": round(avg_seats_per_ride, 1)
        },
        "recommendations": generate_pricing_recommendations(demand_supply_ratio, avg_price, popular_route),
        "period_analyzed": f"{days} days"
    }
    
    return jsonify(insights)


def calculate_growth_rate(from_location, to_location, days):
    """Calculate search growth rate for a route"""
    # Split time periods
    mid_point = datetime.utcnow() - timedelta(days=days//2)
    start_point = datetime.utcnow() - timedelta(days=days)
    
    # Get searches for each period
    recent_searches = SearchHistory.query.filter(
        and_(
            SearchHistory.from_location.ilike(f"%{from_location}%"),
            SearchHistory.to_location.ilike(f"%{to_location}%"),
            SearchHistory.last_searched >= mid_point
        )
    ).with_entities(func.sum(SearchHistory.search_count)).scalar() or 0
    
    earlier_searches = SearchHistory.query.filter(
        and_(
            SearchHistory.from_location.ilike(f"%{from_location}%"),
            SearchHistory.to_location.ilike(f"%{to_location}%"),
            SearchHistory.last_searched >= start_point,
            SearchHistory.last_searched < mid_point
        )
    ).with_entities(func.sum(SearchHistory.search_count)).scalar() or 0
    
    if earlier_searches == 0:
        return 100.0 if recent_searches > 0 else 0.0
    
    growth_rate = ((recent_searches - earlier_searches) / earlier_searches) * 100
    return round(growth_rate, 1)


def calculate_price_distribution(prices):
    """Calculate price distribution buckets"""
    if not prices:
        return {}
        
    buckets = {"low": 0, "medium": 0, "high": 0}
    avg_price = sum(prices) / len(prices)
    
    for price in prices:
        if price < avg_price * 0.8:
            buckets["low"] += 1
        elif price > avg_price * 1.2:
            buckets["high"] += 1
        else:
            buckets["medium"] += 1
    
    total = len(prices)
    return {
        "low": round(buckets["low"] / total * 100, 1),
        "medium": round(buckets["medium"] / total * 100, 1), 
        "high": round(buckets["high"] / total * 100, 1)
    }


def calculate_recommended_price(avg_price, demand_supply_ratio):
    """Calculate recommended price based on market conditions"""
    base_price = avg_price
    
    # Adjust based on demand/supply
    if demand_supply_ratio > 2.0:  # High demand, low supply
        recommended = base_price * 1.15
    elif demand_supply_ratio > 1.5:
        recommended = base_price * 1.08
    elif demand_supply_ratio < 0.5:  # Low demand, high supply
        recommended = base_price * 0.92
    elif demand_supply_ratio < 0.8:
        recommended = base_price * 0.96
    else:
        recommended = base_price
    
    return round(recommended, 2)


def get_market_temperature(demand_supply_ratio):
    """Get market temperature description"""
    if demand_supply_ratio > 2.0:
        return "🔥 Hot - High demand, limited supply"
    elif demand_supply_ratio > 1.5:
        return "🌡️ Warm - Good demand"
    elif demand_supply_ratio > 0.8:
        return "🌡️ Balanced - Normal market conditions"
    elif demand_supply_ratio > 0.5:
        return "❄️ Cool - Lower demand"
    else:
        return "🧊 Cold - Oversupplied market"


def generate_pricing_recommendations(demand_supply_ratio, avg_price, popular_route):
    """Generate pricing recommendations"""
    recommendations = []
    
    if demand_supply_ratio > 1.5:
        recommendations.append({
            "type": "increase_price",
            "message": f"Consider pricing above ${avg_price:.2f} due to high demand",
            "confidence": "high"
        })
    elif demand_supply_ratio < 0.5:
        recommendations.append({
            "type": "competitive_pricing", 
            "message": f"Consider competitive pricing below ${avg_price:.2f} to attract riders",
            "confidence": "medium"
        })
    
    if popular_route and popular_route.popularity_score > 70:
        recommendations.append({
            "type": "premium_pricing",
            "message": "This is a popular route - riders may pay premium prices",
            "confidence": "medium"
        })
    
    recommendations.append({
        "type": "timing",
        "message": "Consider posting rides 2-3 days in advance for better visibility",
        "confidence": "high"
    })
    
    return recommendations


@smart_bp.route("/rides/optimize", methods=["POST"])
@token_required
def optimize_ride():
    """Get optimization recommendations for a ride or route planning"""
    data = request.get_json() or {}
    
    from_location = data.get("from", "").strip()
    to_location = data.get("to", "").strip()
    departure_date_str = data.get("departure_date", "")
    ride_id = data.get("ride_id")  # Optional: for existing rides
    
    if not from_location:
        return jsonify({"error": "from location is required"}), 400
        
    try:
        departure_date = datetime.fromisoformat(departure_date_str.replace('Z', '+00:00')) if departure_date_str else datetime.utcnow() + timedelta(days=2)
    except ValueError:
        return jsonify({"error": "Invalid departure_date format"}), 400
    
    # If optimizing existing ride
    if ride_id:
        ride = Ride.query.get(ride_id)
        if not ride:
            return jsonify({"error": "Ride not found"}), 404
            
        profile = g.current_user
        if ride.driver_id != profile.id:
            return jsonify({"error": "You can only optimize your own rides"}), 403
            
        optimization = get_optimization_recommendations(ride)
        return jsonify({
            "type": "existing_ride",
            "ride_id": ride_id,
            **optimization
        })
    
    # For new ride planning
    if not to_location:
        return jsonify({"error": "to location is required for new ride planning"}), 400
    
    # Get comprehensive analysis
    optimal_timing = get_optimal_posting_time(from_location, to_location)
    competition_analysis = analyze_route_competition(from_location, to_location, departure_date)
    demand_forecast = get_demand_forecast(from_location, to_location, departure_date)
    alternatives = suggest_alternative_routes(from_location, departure_date)
    
    # Generate overall recommendation
    overall_score = calculate_overall_route_score(competition_analysis, demand_forecast)
    
    optimization_data = {
        "type": "route_planning",
        "route": {
            "from_location": from_location,
            "to_location": to_location,
            "departure_date": departure_date.isoformat()
        },
        "overall_score": overall_score,
        "recommendation": get_route_recommendation(overall_score),
        "analysis": {
            "optimal_timing": optimal_timing,
            "competition": competition_analysis,
            "demand_forecast": demand_forecast
        },
        "alternatives": alternatives,
        "action_items": generate_action_items(optimal_timing, competition_analysis, demand_forecast)
    }
    
    return jsonify(optimization_data)


def calculate_overall_route_score(competition_analysis, demand_forecast):
    """Calculate overall route opportunity score"""
    score = 50  # Base score
    
    # Competition adjustment
    competition_scores = {"low": 20, "medium": 0, "high": -15}
    score += competition_scores.get(competition_analysis["competition_level"], 0)
    
    # Demand adjustment  
    demand_scores = {"high": 25, "medium": 10, "low": -5, "very_low": -15}
    score += demand_scores.get(demand_forecast["demand_level"], 0)
    
    # Confidence penalty
    if demand_forecast["confidence"] == "low":
        score -= 10
    
    return max(0, min(100, score))


def get_route_recommendation(overall_score):
    """Get route recommendation based on overall score"""
    if overall_score >= 80:
        return {
            "level": "excellent",
            "message": "🌟 Excellent opportunity! High demand with low competition.",
            "action": "Post this ride with confidence at competitive pricing."
        }
    elif overall_score >= 60:
        return {
            "level": "good", 
            "message": "✅ Good opportunity with solid potential for bookings.",
            "action": "Post the ride and consider highlighting unique features."
        }
    elif overall_score >= 40:
        return {
            "level": "moderate",
            "message": "⚡ Moderate opportunity. Some challenges but still viable.",
            "action": "Consider optimizations like flexible pickup or competitive pricing."
        }
    else:
        return {
            "level": "challenging",
            "message": "⚠️ Challenging route with high competition or low demand.",
            "action": "Consider alternative routes or different timing."
        }


def generate_action_items(optimal_timing, competition_analysis, demand_forecast):
    """Generate specific action items for the driver"""
    actions = []
    
    # Timing actions
    if optimal_timing["confidence"] != "low":
        peak_hours = optimal_timing["peak_search_hours"]
        actions.append({
            "category": "timing",
            "priority": "high",
            "action": f"Post your ride during peak search hours: {', '.join(map(str, peak_hours))}:00",
            "reason": "Maximum visibility when riders are actively searching"
        })
    
    actions.append({
        "category": "timing",
        "priority": "medium", 
        "action": f"Post {optimal_timing['recommended_days_ahead']} days in advance",
        "reason": "Optimal balance between early visibility and urgency"
    })
    
    # Competition actions
    if competition_analysis["competition_level"] == "high":
        actions.append({
            "category": "competition",
            "priority": "high",
            "action": f"Price competitively around ${competition_analysis['suggested_price_range']['min']:.2f}-{competition_analysis['suggested_price_range']['max']:.2f}",
            "reason": "Stand out in a competitive market"
        })
        
        actions.append({
            "category": "differentiation", 
            "priority": "medium",
            "action": "Highlight your driver rating and unique features (AC, music, etc.)",
            "reason": "Differentiate from competition"
        })
    
    # Demand actions
    if demand_forecast["demand_level"] in ["low", "very_low"]:
        actions.append({
            "category": "flexibility",
            "priority": "high", 
            "action": "Offer flexible pickup and dropoff locations",
            "reason": "Attract more riders in a low-demand market"
        })
    
    return actions


@smart_bp.route("/dashboard/summary", methods=["GET"])
@token_required
def dashboard_summary():
    """Get comprehensive dashboard summary for smart features"""
    profile = g.current_user
    days = int(request.args.get("days", 7))
    
    # Get user's recent search patterns
    search_patterns = get_user_search_patterns(profile.id, limit=5)
    
    # Get trending routes
    trending = get_trending_routes(limit=5, days=days)
    
    # Get user's analytics summary
    analytics = get_search_analytics_summary(user_id=profile.id, days=30)
    
    # Get personalized recommendations
    recommendations = []
    
    if search_patterns:
        most_frequent = search_patterns[0]
        recommendations.append({
            "type": "repeat_search",
            "title": "Quick Search",
            "message": f"Search {most_frequent['from_location']} → {most_frequent['to_location']} again?",
            "action_data": {
                "from": most_frequent['from_location'],
                "to": most_frequent['to_location']
            }
        })
    
    if trending:
        hot_route = trending[0]
        recommendations.append({
            "type": "trending_route",
            "title": "Trending Route",
            "message": f"🔥 {hot_route['from_location']} → {hot_route['to_location']} is trending",
            "action_data": {
                "from": hot_route['from_location'], 
                "to": hot_route['to_location']
            }
        })
    
    # Smart insights
    insights = []
    
    if analytics and analytics['total_searches'] > 0:
        if analytics['avg_results_per_search'] < 2:
            insights.append({
                "type": "search_tip",
                "icon": "💡",
                "message": "Try increasing search radius - you're finding few results",
                "action": "Use advanced search with larger distance"
            })
        
        if len(analytics['popular_routes']) >= 3:
            insights.append({
                "type": "pattern_detected",
                "icon": "📊", 
                "message": f"You frequently search {len(analytics['popular_routes'])} different routes",
                "action": "Save favorite routes for quick access"
            })
    
    # Recent activity summary
    activity_summary = {
        "total_searches": analytics['total_searches'] if analytics else 0,
        "unique_routes": analytics['unique_routes'] if analytics else 0,
        "avg_results": analytics['avg_results_per_search'] if analytics else 0
    }
    
    return jsonify({
        "summary": {
            "period_days": days,
            "activity": activity_summary,
            "search_patterns": search_patterns[:3],  # Top 3
            "trending_routes": trending[:3],  # Top 3
        },
        "recommendations": recommendations,
        "insights": insights,
        "quick_actions": [
            {
                "type": "advanced_search",
                "title": "Advanced Search", 
                "description": "Use smart filters and geolocation"
            },
            {
                "type": "popular_routes",
                "title": "Browse Popular Routes",
                "description": "See what others are searching for"
            }
        ]
    })