"""
Ride optimization utilities for drivers and intelligent route suggestions
"""

from datetime import datetime, timedelta
from sqlalchemy import and_, func
from ..models import db, Ride, SearchHistory, PopularRoute


def get_optimal_posting_time(from_location, to_location):
    """Analyze historical data to suggest optimal posting time"""
    
    # Get search patterns for this route
    search_history = SearchHistory.query.filter(
        and_(
            SearchHistory.from_location.ilike(f"%{from_location}%"),
            SearchHistory.to_location.ilike(f"%{to_location}%"),
            SearchHistory.last_searched >= datetime.utcnow() - timedelta(days=30)
        )
    ).all()
    
    if not search_history:
        return {
            "recommended_days_ahead": 2,
            "peak_search_hours": [9, 17, 20],
            "confidence": "low",
            "message": "Limited data available. General recommendation: post 2 days ahead during peak hours."
        }
    
    # Analyze search timing patterns
    hourly_searches = {}
    days_ahead_searches = {}
    
    for history in search_history:
        if history.last_searched:
            hour = history.last_searched.hour
            hourly_searches[hour] = hourly_searches.get(hour, 0) + history.search_count
    
    # Find peak search hours
    peak_hours = sorted(hourly_searches.items(), key=lambda x: x[1], reverse=True)[:3]
    peak_hours = [hour for hour, _ in peak_hours]
    
    return {
        "recommended_days_ahead": 2,  # Standard recommendation
        "peak_search_hours": peak_hours if peak_hours else [9, 17, 20],
        "confidence": "medium" if len(search_history) > 5 else "low",
        "message": f"Based on {len(search_history)} recent searches, post during peak hours for better visibility."
    }


def analyze_route_competition(from_location, to_location, departure_date):
    """Analyze competition for a specific route and date"""
    
    # Define date range (same day)
    start_of_day = departure_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    
    # Get competing rides
    competing_rides = Ride.query.filter(
        and_(
            Ride.start_location.ilike(f"%{from_location}%"),
            Ride.end_location.ilike(f"%{to_location}%"),
            Ride.departure_time >= start_of_day,
            Ride.departure_time < end_of_day,
            Ride.status.in_(["available", "scheduled"])
        )
    ).all()
    
    if not competing_rides:
        return {
            "competition_level": "low",
            "competing_rides": 0,
            "average_price": None,
            "total_available_seats": 0,
            "recommendation": "Great opportunity! No direct competition for this route and date.",
            "suggested_price_range": {"min": 15, "max": 40}
        }
    
    # Calculate competition metrics
    total_seats = sum(ride.available_seats for ride in competing_rides)
    prices = [float(ride.price_per_seat) for ride in competing_rides]
    avg_price = sum(prices) / len(prices)
    
    # Determine competition level
    competition_level = "high" if len(competing_rides) >= 5 else "medium" if len(competing_rides) >= 2 else "low"
    
    # Calculate suggested price range
    min_suggested = max(min(prices) * 0.95, 10) if prices else 15
    max_suggested = max(prices) * 1.1 if prices else 40
    
    recommendations = []
    if competition_level == "high":
        recommendations.append("Consider competitive pricing to stand out")
        recommendations.append("Highlight unique features like pickup flexibility")
    elif competition_level == "medium":
        recommendations.append("Price competitively while showcasing your driver rating")
    else:
        recommendations.append("You have good market positioning for this route")
    
    return {
        "competition_level": competition_level,
        "competing_rides": len(competing_rides),
        "average_price": round(avg_price, 2),
        "total_available_seats": total_seats,
        "recommendation": recommendations[0],
        "all_recommendations": recommendations,
        "suggested_price_range": {
            "min": round(min_suggested, 2),
            "max": round(max_suggested, 2)
        }
    }


def get_demand_forecast(from_location, to_location, target_date):
    """Forecast demand for a route on a specific date"""
    
    # Get historical search data
    search_history = SearchHistory.query.filter(
        and_(
            SearchHistory.from_location.ilike(f"%{from_location}%"),
            SearchHistory.to_location.ilike(f"%{to_location}%"),
            SearchHistory.last_searched >= datetime.utcnow() - timedelta(days=60)
        )
    ).all()
    
    if not search_history:
        return {
            "demand_level": "unknown",
            "confidence": "low",
            "total_searches": 0,
            "weekly_average": 0,
            "recommendation": "Limited historical data. Monitor search trends after posting."
        }
    
    # Calculate demand metrics
    total_searches = sum(history.search_count for history in search_history)
    weekly_average = total_searches / max(8, 1)  # 60 days ≈ 8 weeks
    
    # Determine demand level
    if weekly_average >= 20:
        demand_level = "high"
    elif weekly_average >= 10:
        demand_level = "medium"
    elif weekly_average >= 3:
        demand_level = "low"
    else:
        demand_level = "very_low"
    
    # Day of week analysis
    dow_searches = {}
    target_dow = target_date.weekday()  # 0 = Monday
    
    for history in search_history:
        if history.last_searched:
            dow = history.last_searched.weekday()
            dow_searches[dow] = dow_searches.get(dow, 0) + history.search_count
    
    target_dow_searches = dow_searches.get(target_dow, 0)
    avg_dow_searches = sum(dow_searches.values()) / max(len(dow_searches), 1)
    
    # Day-specific demand adjustment
    dow_multiplier = target_dow_searches / max(avg_dow_searches, 1) if avg_dow_searches > 0 else 1
    adjusted_demand = weekly_average * dow_multiplier
    
    recommendations = {
        "high": "Excellent demand! Price competitively and post early for best results.",
        "medium": "Good demand expected. Standard pricing recommended.",
        "low": "Limited demand. Consider flexible pickup options to attract riders.",
        "very_low": "Low demand route. Consider alternative routes or times."
    }
    
    return {
        "demand_level": demand_level,
        "confidence": "high" if len(search_history) > 10 else "medium",
        "total_searches": total_searches,
        "weekly_average": round(weekly_average, 1),
        "day_of_week_factor": round(dow_multiplier, 2),
        "adjusted_demand": round(adjusted_demand, 1),
        "recommendation": recommendations[demand_level]
    }


def suggest_alternative_routes(from_location, departure_date, max_suggestions=5):
    """Suggest alternative high-demand routes from the same starting location"""
    
    # Get popular routes from this location
    popular_routes = PopularRoute.query.filter(
        PopularRoute.from_location.ilike(f"%{from_location}%")
    ).order_by(
        PopularRoute.popularity_score.desc()
    ).limit(max_suggestions * 2).all()  # Get more to filter
    
    if not popular_routes:
        return {
            "suggestions": [],
            "message": "No alternative route suggestions available for this location."
        }
    
    suggestions = []
    for route in popular_routes:
        # Analyze competition for this alternative route
        competition = analyze_route_competition(
            route.from_location, 
            route.to_location, 
            departure_date
        )
        
        # Calculate opportunity score
        opportunity_score = route.popularity_score
        if competition["competition_level"] == "low":
            opportunity_score += 20
        elif competition["competition_level"] == "high":
            opportunity_score -= 10
        
        suggestion = {
            "to_location": route.to_location,
            "popularity_score": route.popularity_score,
            "opportunity_score": round(opportunity_score, 1),
            "search_count": route.search_count,
            "estimated_price": f"${float(route.avg_price):.2f}" if route.avg_price else "N/A",
            "competition_level": competition["competition_level"],
            "recommendation_reason": generate_route_recommendation_reason(route, competition)
        }
        suggestions.append(suggestion)
    
    # Sort by opportunity score
    suggestions.sort(key=lambda x: x["opportunity_score"], reverse=True)
    
    return {
        "suggestions": suggestions[:max_suggestions],
        "message": f"Found {len(suggestions)} alternative route suggestions based on demand and competition."
    }


def generate_route_recommendation_reason(route, competition):
    """Generate a human-readable reason for route recommendation"""
    reasons = []
    
    if route.popularity_score > 70:
        reasons.append("High search demand")
    elif route.popularity_score > 40:
        reasons.append("Moderate search demand")
    
    if competition["competition_level"] == "low":
        reasons.append("low competition")
    elif competition["competition_level"] == "medium":
        reasons.append("moderate competition")
    else:
        reasons.append("high competition")
    
    if route.avg_price and float(route.avg_price) > 25:
        reasons.append("good pricing potential")
    
    return " • ".join(reasons) if reasons else "Alternative route option"


def calculate_ride_visibility_score(ride):
    """Calculate how visible a ride is likely to be in search results"""
    score = 0
    
    # Base score from ride attributes
    if ride.available_seats >= 3:
        score += 15  # More seats = more attractive
    
    if ride.pickup_flexibility > 5:
        score += 10  # Flexible pickup
    
    if ride.dropoff_flexibility > 5:
        score += 10  # Flexible dropoff
    
    # Driver quality score
    if ride.driver_profile:
        if ride.driver_profile.driver_rating >= 4.5:
            score += 20
        elif ride.driver_profile.driver_rating >= 4.0:
            score += 15
        elif ride.driver_profile.driver_rating >= 3.5:
            score += 10
        
        # Experience bonus
        if ride.driver_profile.total_rides >= 50:
            score += 15
        elif ride.driver_profile.total_rides >= 20:
            score += 10
        elif ride.driver_profile.total_rides >= 5:
            score += 5
    
    # Timing bonus (rides posted 2-4 days ahead get boost)
    if ride.created_at and ride.departure_time:
        days_ahead = (ride.departure_time - ride.created_at).days
        if 2 <= days_ahead <= 4:
            score += 10
        elif days_ahead == 1:
            score += 5
    
    # Price competitiveness (would need market data)
    # This would be calculated based on similar routes
    
    return min(score, 100)  # Cap at 100


def get_optimization_recommendations(ride):
    """Get specific recommendations to optimize ride visibility and bookings"""
    recommendations = []
    
    visibility_score = calculate_ride_visibility_score(ride)
    
    if visibility_score < 40:
        recommendations.append({
            "type": "urgent",
            "message": "Your ride visibility is low. Consider the suggestions below to improve it.",
            "priority": "high"
        })
    
    # Specific recommendations
    if ride.available_seats < 2:
        recommendations.append({
            "type": "seats",
            "message": "Consider offering more seats if possible - rides with 3+ seats are more discoverable.",
            "priority": "medium"
        })
    
    if ride.pickup_flexibility < 5:
        recommendations.append({
            "type": "flexibility", 
            "message": "Adding pickup flexibility can make your ride more attractive to potential riders.",
            "priority": "low"
        })
    
    if ride.driver_profile and ride.driver_profile.driver_rating < 4.0:
        recommendations.append({
            "type": "rating",
            "message": "Focus on providing excellent service to improve your driver rating.",
            "priority": "high"
        })
    
    # Timing recommendations
    if ride.created_at and ride.departure_time:
        days_ahead = (ride.departure_time - ride.created_at).days
        if days_ahead > 7:
            recommendations.append({
                "type": "timing",
                "message": "Posting too far in advance can reduce visibility. 2-4 days ahead is optimal.",
                "priority": "medium"
            })
        elif days_ahead < 1:
            recommendations.append({
                "type": "timing",
                "message": "Last-minute posts have lower visibility. Try posting 2-4 days ahead next time.",
                "priority": "low"
            })
    
    return {
        "visibility_score": visibility_score,
        "recommendations": recommendations,
        "overall_assessment": get_overall_assessment(visibility_score)
    }


def get_overall_assessment(visibility_score):
    """Get overall assessment based on visibility score"""
    if visibility_score >= 80:
        return "Excellent - Your ride is highly optimized for maximum visibility"
    elif visibility_score >= 60:
        return "Good - Your ride has strong visibility with room for minor improvements"
    elif visibility_score >= 40:
        return "Fair - Consider implementing some optimizations to improve visibility"
    else:
        return "Needs Improvement - Several optimizations needed to improve ride visibility"