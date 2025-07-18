from dotenv import load_dotenv
from pathlib import Path
import os

# Load .env.development or fallback to .env
env_path = Path(".env.development")
load_dotenv(dotenv_path=env_path)

from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV") == "development")