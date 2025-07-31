import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Strava & MApbox API keys
    STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
    STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
    REDIRECT_URI = os.getenv('REDIRECT_URI')
    MAPBOX_TOKEN = os.getenv('MAPBOX_TOKEN')
    STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
    STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
    STRAVA_API_URL = "https://www.strava.com/api/v3"
    SCOPE = "read,activity:read_all"
    
    # Database configuration
    db_url = os.getenv('DATABASE_URL')
    
    if db_url:
        SQLALCHEMY_DATABASE_URI = db_url.replace("postgres://", "postgresql://", 1)
    else:
        # Default to local PostgreSQL database for development
        SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg://milo@localhost:5432/my_local_db'