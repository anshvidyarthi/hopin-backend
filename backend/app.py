from flask import Flask
from flask_cors import CORS
from backend.models import db
from backend.routes.auth import auth_bp
from backend.routes.user import user_bp
from .routes.riders import rider_bp
from .routes.driver import driver_bp
from .routes.validateLicense import validate_bp
from .routes.messages import messages_bp
from .routes.reviews import review_bp
from .routes.smart_features import smart_bp
import os
from backend.config import Config
from backend.socket_handlers import socketio

def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
    app.config.from_object(Config)
    db.init_app(app)

    socketio.init_app(
        app,
        cors_allowed_origins="*",      # ← allow every origin
        cors_credentials=True,
    )
    CORS(app, supports_credentials=True, origins="*")

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(rider_bp, url_prefix='/rider')
    app.register_blueprint(driver_bp, url_prefix='/driver')
    app.register_blueprint(messages_bp, url_prefix='/messages')
    app.register_blueprint(validate_bp, url_prefix='/validate')
    app.register_blueprint(review_bp, url_prefix='/reviews')
    app.register_blueprint(smart_bp, url_prefix='/smart')

    return app
