from dotenv import load_dotenv
from pathlib import Path
import os

# Load .env.development or fallback to .env
env_path = Path(".env.development")
load_dotenv(dotenv_path=env_path)

from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",  # ← this exposes it to local network
        port=5000,
        debug=os.getenv("FLASK_ENV") == "development"
    )