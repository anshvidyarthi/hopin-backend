"""
Search analytics and user behavior tracking utilities
"""

from datetime import datetime
from ..models import db, SearchHistory, PopularRoute


def log_search_analytics(user_id, search_params, results_count):
    """Log search for analytics and popular route tracking"""
    try:
        from_location = search_params.get('from', '')
        to_location = search_params.get('to', '')
        
        if not from_location or not to_location:
            return False
            
        # Update or create search history
        search_history = SearchHistory.query.filter_by(
            user_id=user_id,
            from_location=from_location,
            to_location=to_location
        ).first()
        
        if search_history:
            search_history.search_count += 1
            search_history.results_count = results_count
            search_history.last_searched = datetime.utcnow()
        else:
            search_history = SearchHistory(
                user_id=user_id,
                from_location=from_location,
                to_location=to_location,
                from_lat=search_params.get('from_lat'),
                from_lng=search_params.get('from_lng'),
                to_lat=search_params.get('to_lat'),
                to_lng=search_params.get('to_lng'),
                search_count=1,
                results_count=results_count
            )
            db.session.add(search_history)
        
        # Update popular routes
        popular_route = PopularRoute.query.filter_by(
            from_location=from_location,
            to_location=to_location
        ).first()
        
        if popular_route:
            popular_route.search_count += 1
            popular_route.updated_at = datetime.utcnow()
            # Update popularity score based on recent activity
            popular_route.popularity_score = calculate_route_popularity_score(popular_route)
        else:
            popular_route = PopularRoute(
                from_location=from_location,
                to_location=to_location,
                from_lat=search_params.get('from_lat'),
                from_lng=search_params.get('from_lng'),
                to_lat=search_params.get('to_lat'),
                to_lng=search_params.get('to_lng'),
                search_count=1,
                popularity_score=1.0
            )
            db.session.add(popular_route)
            
        db.session.commit()
        return True
        
    except Exception as e:
        print(f"Search analytics logging failed: {e}")
        db.session.rollback()
        return False


def calculate_route_popularity_score(popular_route):
    """Calculate popularity score for a route based on multiple factors"""
    score = 0.0
    
    # Base score from search count (logarithmic scale)
    import math
    search_score = min(math.log10(popular_route.search_count + 1) * 20, 60)
    score += search_score
    
    # Ride count bonus
    ride_score = min(popular_route.ride_count * 5, 30)
    score += ride_score
    
    # Recent activity bonus
    if popular_route.updated_at:
        days_since_update = (datetime.utcnow() - popular_route.updated_at).days
        if days_since_update <= 7:
            recency_score = 10 - (days_since_update * 1.4)
            score += max(0, recency_score)
    
    return round(score, 2)


def get_user_search_patterns(user_id, limit=10):
    """Get user's search patterns for personalization"""
    search_history = SearchHistory.query.filter_by(
        user_id=user_id
    ).order_by(
        SearchHistory.search_count.desc(),
        SearchHistory.last_searched.desc()
    ).limit(limit).all()
    
    patterns = []
    for history in search_history:
        patterns.append({
            'from_location': history.from_location,
            'to_location': history.to_location,
            'search_count': history.search_count,
            'last_searched': history.last_searched.isoformat() if history.last_searched else None,
            'avg_results': history.results_count,
            'coordinates': {
                'from_lat': history.from_lat,
                'from_lng': history.from_lng,
                'to_lat': history.to_lat,
                'to_lng': history.to_lng
            }
        })
    
    return patterns


def get_trending_routes(limit=10, days=7):
    """Get trending routes based on recent search activity"""
    from sqlalchemy import text
    
    # Get routes with high recent activity
    trending_query = text("""
        SELECT * FROM popular_routes 
        WHERE updated_at >= NOW() - INTERVAL :days DAY
        ORDER BY popularity_score DESC, search_count DESC
        LIMIT :limit
    """)
    
    try:
        result = db.session.execute(trending_query, {'days': days, 'limit': limit})
        routes = result.fetchall()
        
        trending = []
        for route in routes:
            trending.append({
                'from_location': route.from_location,
                'to_location': route.to_location,
                'search_count': route.search_count,
                'ride_count': route.ride_count,
                'popularity_score': float(route.popularity_score),
                'avg_price': float(route.avg_price) if route.avg_price else None,
                'coordinates': {
                    'from_lat': route.from_lat,
                    'from_lng': route.from_lng,
                    'to_lat': route.to_lat,
                    'to_lng': route.to_lng
                }
            })
        
        return trending
        
    except Exception as e:
        print(f"Error fetching trending routes: {e}")
        return []


def update_route_ride_stats(from_location, to_location, price_per_seat):
    """Update route statistics when a new ride is posted"""
    try:
        popular_route = PopularRoute.query.filter_by(
            from_location=from_location,
            to_location=to_location
        ).first()
        
        if popular_route:
            popular_route.ride_count += 1
            
            # Update average price
            if popular_route.avg_price:
                # Calculate running average
                total_price = float(popular_route.avg_price) * (popular_route.ride_count - 1) + float(price_per_seat)
                popular_route.avg_price = total_price / popular_route.ride_count
            else:
                popular_route.avg_price = float(price_per_seat)
            
            popular_route.updated_at = datetime.utcnow()
            popular_route.popularity_score = calculate_route_popularity_score(popular_route)
            
            db.session.commit()
            return True
            
    except Exception as e:
        print(f"Error updating route ride stats: {e}")
        db.session.rollback()
        return False


def get_search_analytics_summary(user_id=None, days=30):
    """Get search analytics summary for admin or user"""
    from sqlalchemy import func, text
    
    try:
        base_query = SearchHistory.query
        
        if user_id:
            base_query = base_query.filter_by(user_id=user_id)
            
        # Filter by date range
        if days:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            base_query = base_query.filter(SearchHistory.last_searched >= cutoff_date)
        
        # Basic stats
        total_searches = base_query.with_entities(func.sum(SearchHistory.search_count)).scalar() or 0
        unique_routes = base_query.count()
        avg_results = base_query.with_entities(func.avg(SearchHistory.results_count)).scalar() or 0
        
        # Most popular routes
        popular_routes = base_query.order_by(SearchHistory.search_count.desc()).limit(5).all()
        
        return {
            'total_searches': total_searches,
            'unique_routes': unique_routes,
            'avg_results_per_search': round(float(avg_results), 1),
            'popular_routes': [
                {
                    'from_location': route.from_location,
                    'to_location': route.to_location,
                    'search_count': route.search_count,
                    'avg_results': route.results_count
                } for route in popular_routes
            ]
        }
        
    except Exception as e:
        print(f"Error generating analytics summary: {e}")
        return None