from backend.app import create_app
from backend.models import db

app = create_app()

with app.app_context():
    # Create all missing tables (including notifications)
    db.create_all()
    print("Database updated with new tables")