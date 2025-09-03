#!/usr/bin/env python3
"""
Core Search Data Population
Simplified utility for ride popularity scoring and search vectors
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.models import db, Ride, SearchHistory, Profile, LocationAlias, PopularRoute
from backend.app import create_app
from sqlalchemy import text


class SearchDataManager:
    def __init__(self):
        self.app = create_app()
    
    def calculate_popularity_scores(self):
        """Calculate and update popularity scores for all rides"""
        print("📊 Calculating popularity scores for rides...")
        
        with self.app.app_context():
            try:
                rides = Ride.query.all()
                updated_count = 0
                
                for ride in rides:
                    score = self._calculate_ride_score(ride)
                    if score != ride.popularity_score:
                        ride.popularity_score = score
                        updated_count += 1
                
                db.session.commit()
                print(f"✅ Updated popularity scores for {updated_count} rides")
                return True
                
            except Exception as e:
                print(f"❌ Failed to calculate popularity scores: {e}")
                db.session.rollback()
                return False
    
    def _calculate_ride_score(self, ride):
        """Calculate popularity score for a single ride based on multiple factors"""
        score = 0.0
        
        # Driver quality score (40% weight, 0-40 points)
        if ride.driver_profile and ride.driver_profile.driver_rating:
            driver_score = ride.driver_profile.driver_rating * 8  # 5-star rating -> 40 points
            driver_experience = min(ride.driver_profile.total_rides * 0.5, 10)  # Up to 10 bonus
            score += driver_score + driver_experience
        
        # Request popularity (30% weight, 0-30 points) 
        request_count = len(ride.ride_requests)
        score += min(request_count * 5, 30)
        
        # Recency bonus (20% weight, 0-20 points)
        if ride.departure_time > datetime.utcnow():
            days_until = (ride.departure_time - datetime.utcnow()).days
            if days_until <= 1:
                score += 20  # Departing soon
            elif days_until <= 7:
                score += 15
            elif days_until <= 30:
                score += 10
            else:
                score += 5
        
        # Seat availability (10% weight, 0-10 points)
        if ride.available_seats > 0:
            score += min(ride.available_seats * 2, 10)
        
        return round(score, 2)
    
    def update_search_vectors(self):
        """Update search vectors for full-text search"""
        print("🔍 Updating search vectors...")
        
        with self.app.app_context():
            try:
                # Update ride search vectors
                update_rides_sql = """
                UPDATE rides 
                SET search_vector = LOWER(
                    start_location || ' ' || 
                    end_location || ' ' || 
                    COALESCE(fixed_pickup_location, '')
                )
                WHERE search_vector IS NULL OR search_vector = '';
                """
                
                result = db.session.execute(text(update_rides_sql))
                rides_updated = result.rowcount
                
                db.session.commit()
                print(f"✅ Updated search vectors for {rides_updated} rides")
                return True
                
            except Exception as e:
                print(f"❌ Failed to update search vectors: {e}")
                db.session.rollback()
                return False
    
    def show_summary_stats(self):
        """Show summary statistics of search optimization data"""
        print("📊 Search Optimization Summary:")
        print("-" * 50)
        
        with self.app.app_context():
            try:
                # Count records in each table
                rides_count = Ride.query.count()
                history_count = SearchHistory.query.count()
                aliases_count = LocationAlias.query.count()
                routes_count = PopularRoute.query.count()
                
                print(f"🚗 Total rides: {rides_count:,}")
                print(f"🔍 Search history records: {history_count:,}")
                print(f"📍 Location aliases: {aliases_count:,}")
                print(f"🛣️  Popular routes: {routes_count:,}")
                
                if rides_count > 0:
                    # Show rides with popularity scores
                    scored_rides = Ride.query.filter(Ride.popularity_score > 0).count()
                    print(f"⭐ Rides with popularity scores: {scored_rides:,}")
                    
                    # Show rides with search vectors
                    vector_rides = Ride.query.filter(Ride.search_vector.isnot(None)).count()
                    print(f"🔤 Rides with search vectors: {vector_rides:,}")
                    
                    # Show average popularity score
                    avg_score = db.session.execute(
                        text("SELECT AVG(popularity_score) FROM rides WHERE popularity_score > 0")
                    ).scalar()
                    if avg_score:
                        print(f"📈 Average popularity score: {avg_score:.1f}")
                
                print("-" * 50)
                return True
                
            except Exception as e:
                print(f"❌ Failed to get summary stats: {e}")
                return False
    
    def run_core_optimizations(self):
        """Run core search data optimization tasks"""
        print("🚀 Starting core search data optimization...")
        print("=" * 60)
        
        success_count = 0
        total_tasks = 2
        
        tasks = [
            ("Update search vectors", self.update_search_vectors), 
            ("Calculate popularity scores", self.calculate_popularity_scores),
        ]
        
        for task_name, task_func in tasks:
            print(f"\n📋 {task_name}...")
            if task_func():
                success_count += 1
                print(f"✅ {task_name} completed successfully")
            else:
                print(f"❌ {task_name} failed")
        
        print("\n" + "=" * 60)
        print(f"🏁 Core optimization complete: {success_count}/{len(tasks)} successful")
        
        if success_count == len(tasks):
            print("✅ Core search optimization completed successfully!")
            print()
            self.show_summary_stats()
            print("\n🔥 Your search system core features are optimized!")
            print("\n🚀 Ready for:")
            print("   • Fast coordinate-based searches")
            print("   • Popularity-ranked results")
            print("   • Full-text location search")
            print("   • User search analytics tracking")
        else:
            print("⚠️  Some tasks failed. Check the logs above.")
        
        return success_count == len(tasks)


def main():
    """Main CLI interface"""
    manager = SearchDataManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "all":
            success = manager.run_core_optimizations()
            sys.exit(0 if success else 1)
        elif command == "popularity":
            manager.calculate_popularity_scores()
        elif command == "vectors":
            manager.update_search_vectors()
        elif command == "stats":
            manager.show_summary_stats()
        else:
            print("Unknown command. Available commands: all, popularity, vectors, stats")
            sys.exit(1)
    else:
        print("🔍 Core Search Data Manager")
        print("Available commands:")
        print("  all         - Run core optimization tasks")
        print("  popularity  - Calculate ride popularity scores") 
        print("  vectors     - Update search vectors")
        print("  stats       - Show search data summary")
        print("\nUsage: python populate_search_data.py <command>")
        print("\n🚀 Quick start:")
        print("   python populate_search_data.py all")


if __name__ == "__main__":
    main()