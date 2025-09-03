#!/usr/bin/env python3
"""
Database Index Management Script for Search Optimization
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.models import db
from backend.app import create_app
from sqlalchemy import text


class IndexManager:
    def __init__(self):
        self.app = create_app()
    
    def get_search_indexes(self):
        """Define all search optimization indexes"""
        return {
            # Core ride search indexes
            'rides_coordinates': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rides_coordinates ON rides (start_lat, start_lng, end_lat, end_lng);",
            'rides_departure_time': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rides_departure_time ON rides (departure_time);",
            'rides_status_seats': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rides_status_seats ON rides (status, available_seats);",
            'rides_price': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rides_price ON rides (price_per_seat);",
            'rides_popularity': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rides_popularity ON rides (popularity_score DESC);",
            'rides_driver': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rides_driver_id ON rides (driver_id);",
            
            # Full-text search indexes (PostgreSQL specific)
            'rides_fulltext': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rides_location_text ON rides USING gin (to_tsvector('english', start_location || ' ' || end_location));",
            
            # Location aliases indexes
            'location_aliases_search': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_location_aliases_search ON location_aliases USING gin (to_tsvector('english', alias_name || ' ' || canonical_name));",
            'location_aliases_popularity': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_location_aliases_popularity ON location_aliases (popularity DESC);",
            'location_aliases_coordinates': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_location_aliases_coordinates ON location_aliases (lat, lng);",
            
            # Search history indexes
            'search_history_user': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_history_user ON search_history (user_id);",
            'search_history_locations': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_history_locations ON search_history (from_location, to_location);",
            'search_history_count': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_history_count ON search_history (search_count DESC);",
            'search_history_date': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_history_date ON search_history (last_searched);",
            
            # Popular routes indexes
            'popular_routes_locations': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_popular_routes_locations ON popular_routes (from_location, to_location);",
            'popular_routes_coordinates': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_popular_routes_coordinates ON popular_routes (from_lat, from_lng, to_lat, to_lng);",
            'popular_routes_popularity': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_popular_routes_popularity ON popular_routes (popularity_score DESC);",
            
            # Ride requests optimization
            'ride_requests_rider_status': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ride_requests_rider_status ON ride_requests (rider_id, status);",
            'ride_requests_ride_status': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ride_requests_ride_status ON ride_requests (ride_id, status);",
            
            # Profile indexes for search joins
            'profiles_rating': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_driver_rating ON profiles (driver_rating DESC);",
            'profiles_rides_count': "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_total_rides ON profiles (total_rides DESC);",
        }
    
    def create_all_indexes(self):
        """Create all search optimization indexes"""
        print("🔧 Creating search optimization indexes...")
        print("=" * 60)
        
        indexes = self.get_search_indexes()
        success_count = 0
        
        with self.app.app_context():
            for index_name, index_sql in indexes.items():
                try:
                    print(f"Creating {index_name}...", end=" ")
                    
                    # For CONCURRENTLY indexes, we can't use transactions
                    if "CONCURRENTLY" in index_sql:
                        # Execute without transaction for CONCURRENTLY
                        connection = db.engine.raw_connection()
                        connection.autocommit = True
                        cursor = connection.cursor()
                        cursor.execute(index_sql)
                        cursor.close()
                        connection.close()
                    else:
                        db.session.execute(text(index_sql))
                        db.session.commit()
                    
                    print("✅")
                    success_count += 1
                    
                except Exception as e:
                    print(f"❌ ({str(e)[:30]}...)")
                    if db.session:
                        db.session.rollback()
        
        print("=" * 60)
        print(f"🏁 Index creation complete: {success_count}/{len(indexes)} successful")
        
        if success_count == len(indexes):
            print("✅ All search indexes created successfully!")
            print("🚀 Your database is now optimized for fast search queries!")
        else:
            print("⚠️  Some indexes failed to create. Check PostgreSQL logs for details.")
        
        return success_count == len(indexes)
    
    def drop_search_indexes(self):
        """Drop all search-related indexes"""
        print("🗑️  Dropping search optimization indexes...")
        
        index_names = [
            'idx_rides_coordinates',
            'idx_rides_departure_time', 
            'idx_rides_status_seats',
            'idx_rides_price',
            'idx_rides_popularity',
            'idx_rides_driver_id',
            'idx_rides_location_text',
            'idx_location_aliases_search',
            'idx_location_aliases_popularity',
            'idx_location_aliases_coordinates',
            'idx_search_history_user',
            'idx_search_history_locations',
            'idx_search_history_count',
            'idx_search_history_date',
            'idx_popular_routes_locations',
            'idx_popular_routes_coordinates',
            'idx_popular_routes_popularity',
            'idx_ride_requests_rider_status',
            'idx_ride_requests_ride_status',
            'idx_profiles_driver_rating',
            'idx_profiles_total_rides',
        ]
        
        success_count = 0
        with self.app.app_context():
            for index_name in index_names:
                try:
                    print(f"Dropping {index_name}...", end=" ")
                    db.session.execute(text(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name};"))
                    db.session.commit()
                    print("✅")
                    success_count += 1
                    
                except Exception as e:
                    print(f"❌ ({str(e)[:20]}...)")
                    db.session.rollback()
        
        print(f"🏁 Dropped {success_count}/{len(index_names)} indexes")
    
    def analyze_tables(self):
        """Update table statistics for better query planning"""
        print("📊 Analyzing tables for query optimization...")
        
        tables = ['rides', 'location_aliases', 'search_history', 'popular_routes', 'profiles', 'ride_requests']
        
        with self.app.app_context():
            for table in tables:
                try:
                    print(f"Analyzing {table}...", end=" ")
                    db.session.execute(text(f"ANALYZE {table};"))
                    db.session.commit()
                    print("✅")
                except Exception as e:
                    print(f"❌ ({str(e)[:20]}...)")
                    db.session.rollback()
    
    def check_index_usage(self):
        """Check index usage statistics (PostgreSQL specific)"""
        print("📈 Checking index usage statistics...")
        
        with self.app.app_context():
            try:
                query = """
                SELECT 
                    schemaname,
                    relname as tablename,
                    indexrelname as indexname,
                    idx_scan as times_used,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes 
                WHERE indexrelname LIKE 'idx_%'
                ORDER BY idx_scan DESC;
                """
                
                result = db.session.execute(text(query))
                rows = result.fetchall()
                
                if rows:
                    print("\n📊 Index Usage Statistics:")
                    print("-" * 90)
                    print(f"{'Index Name':<35} {'Times Used':<12} {'Size':<10} {'Tuples Read':<12}")
                    print("-" * 90)
                    
                    for row in rows:
                        print(f"{row.indexname:<35} {row.times_used:<12} {row.index_size:<10} {row.tuples_read:<12}")
                        
                    print(f"\n📋 Total search indexes: {len(rows)}")
                else:
                    print("📭 No index usage statistics available yet")
                    print("💡 Run some search queries first, then check again")
                    
            except Exception as e:
                print(f"❌ Failed to get index statistics: {e}")


def main():
    """Main CLI interface"""
    manager = IndexManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "create":
            success = manager.create_all_indexes()
            sys.exit(0 if success else 1)
        elif command == "drop":
            confirm = input("⚠️  Are you sure you want to drop all search indexes? (y/N): ")
            if confirm.lower() == 'y':
                manager.drop_search_indexes()
            else:
                print("❌ Operation cancelled")
        elif command == "analyze":
            manager.analyze_tables()
        elif command == "stats":
            manager.check_index_usage()
        else:
            print("Unknown command. Available commands: create, drop, analyze, stats")
            sys.exit(1)
    else:
        print("🗂️  Database Index Management")
        print("Available commands:")
        print("  create   - Create all search optimization indexes")
        print("  drop     - Drop all search optimization indexes") 
        print("  analyze  - Update table statistics for better query planning")
        print("  stats    - Show index usage statistics")
        print("\nUsage: python manage_indexes.py <command>")
        print("\n🚀 Quick start:")
        print("   python manage_indexes.py create")


if __name__ == "__main__":
    main()