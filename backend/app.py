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
import os
from backend.config import Config
from backend.socket_handlers import socketio

def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
    app.config.from_object('backend.config.Config')
    socketio.init_app(app)
    socketio.run(app, debug=True)

    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:8080")

    #CORS(app, supports_credentials=True, origins=[FRONTEND_ORIGIN])
    CORS(app, supports_credentials=True)
    db.init_app(app)

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(rider_bp, url_prefix='/rider')
    app.register_blueprint(driver_bp, url_prefix='/driver')
    app.register_blueprint(messages_bp, url_prefix='/messages')
    app.register_blueprint(validate_bp, url_prefix='/validate')
    app.register_blueprint(review_bp, url_prefix='/reviews')

    return app
