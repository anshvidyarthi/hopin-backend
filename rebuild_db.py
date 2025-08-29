from backend.app import create_app
from backend.models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    db.session.execute(text("DROP SCHEMA public CASCADE"))
    db.session.execute(text("CREATE SCHEMA public"))
    db.session.commit()

    db.create_all()
    print("Database schema rebuilt from scratch")