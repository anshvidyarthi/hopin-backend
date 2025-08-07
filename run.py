from dotenv import load_dotenv
from pathlib import Path
import os

# Load .env.development or fallback to .env
env_path = Path(".env.development")
load_dotenv(dotenv_path=env_path)

from backend.app import create_app
from backend.socket_handlers import socketio

app = create_app()

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=(os.getenv("FLASK_ENV") == "development"),
        allow_unsafe_werkzeug=True
    )