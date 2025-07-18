from backend.app import create_app
from backend.models import db

app = create_app()

with app.app_context():
    db.create_all()