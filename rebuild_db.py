from backend.app import create_app
from backend.models import db
from sqlalchemy import text
import sys

app = create_app()

def create_search_indexes():
    """Create all search optimization indexes"""
    print("Creating search optimization indexes...")
    
    indexes_sql = [
        # Core ride search indexes
        "CREATE INDEX IF NOT EXISTS idx_rides_coordinates ON rides (start_lat, start_lng, end_lat, end_lng);",
        "CREATE INDEX IF NOT EXISTS idx_rides_departure_time ON rides (departure_time);",
        "CREATE INDEX IF NOT EXISTS idx_rides_status_seats ON rides (status, available_seats);",
        "CREATE INDEX IF NOT EXISTS idx_rides_price ON rides (price_per_seat);",
        "CREATE INDEX IF NOT EXISTS idx_rides_popularity ON rides (popularity_score DESC);",
        "CREATE INDEX IF NOT EXISTS idx_rides_driver_id ON rides (driver_id);",
        
        # Full-text search on location names
        "CREATE INDEX IF NOT EXISTS idx_rides_location_text ON rides USING gin (to_tsvector('english', start_location || ' ' || end_location));",
        
        # Location aliases indexes
        "CREATE INDEX IF NOT EXISTS idx_location_aliases_search ON location_aliases USING gin (to_tsvector('english', alias_name || ' ' || canonical_name));",
        "CREATE INDEX IF NOT EXISTS idx_location_aliases_popularity ON location_aliases (popularity DESC);",
        "CREATE INDEX IF NOT EXISTS idx_location_aliases_coordinates ON location_aliases (lat, lng);",
        
        # Search history indexes
        "CREATE INDEX IF NOT EXISTS idx_search_history_user ON search_history (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_search_history_locations ON search_history (from_location, to_location);",
        "CREATE INDEX IF NOT EXISTS idx_search_history_count ON search_history (search_count DESC);",
        "CREATE INDEX IF NOT EXISTS idx_search_history_date ON search_history (last_searched);",
        
        # Popular routes indexes
        "CREATE INDEX IF NOT EXISTS idx_popular_routes_locations ON popular_routes (from_location, to_location);",
        "CREATE INDEX IF NOT EXISTS idx_popular_routes_coordinates ON popular_routes (from_lat, from_lng, to_lat, to_lng);",
        "CREATE INDEX IF NOT EXISTS idx_popular_routes_popularity ON popular_routes (popularity_score DESC);",
        
        # Ride requests indexes
        "CREATE INDEX IF NOT EXISTS idx_ride_requests_rider_status ON ride_requests (rider_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_ride_requests_ride_status ON ride_requests (ride_id, status);",
        
        # Profile indexes for search joins
        "CREATE INDEX IF NOT EXISTS idx_profiles_driver_rating ON profiles (driver_rating DESC);",
        "CREATE INDEX IF NOT EXISTS idx_profiles_total_rides ON profiles (total_rides DESC);",
    ]
    
    success_count = 0
    for sql in indexes_sql:
        try:
            db.session.execute(text(sql))
            success_count += 1
        except Exception as e:
            print(f"Warning: Failed to create index: {sql[:50]}... - {str(e)}")
    
    db.session.commit()
    print(f"✅ Created {success_count}/{len(indexes_sql)} indexes successfully")
    return success_count

def main():
    print("🔄 Rebuilding database with core search optimization...")
    print("=" * 60)
    
    with app.app_context():
        try:
            # Drop and recreate schema
            print("Dropping existing schema...")
            db.session.execute(text("DROP SCHEMA public CASCADE"))
            db.session.execute(text("CREATE SCHEMA public"))
            db.session.commit()
            print("✅ Schema dropped and recreated")
            
            # Create all tables
            print("Creating all tables...")
            db.create_all()
            print("✅ All tables created successfully")
            
            # Create search indexes
            index_count = create_search_indexes()
            
            print("=" * 60)
            print("🎉 Database rebuilt successfully!")
            print("\n📊 Your database now includes:")
            print("  ✅ Enhanced Ride model with popularity_score and search_vector")
            print("  ✅ LocationAlias table for smart location mapping (empty)")
            print("  ✅ SearchHistory table for user analytics (empty)")
            print("  ✅ PopularRoute table for trending routes (empty)")
            print(f"  ✅ {index_count} performance indexes for fast queries")
            print("  ✅ Full-text search capabilities")
            
            print("\n🚀 Ready for:")
            print("• Fast coordinate-based searches")
            print("• Popularity-ranked results")
            print("• Smart location alias matching")
            print("• Popular route tracking")
            print("• User search analytics")
            print("• Full-text location search")
            
            return True
            
        except Exception as e:
            print(f"❌ Database rebuild failed: {e}")
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)