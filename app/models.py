import uuid
from datetime import datetime
from . import db # Import the db instance from the app package

class User(db.Model):
    """User model for storing Strava user data."""
    # ** Include refresh token and expires_at for future use **    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    access_token = db.Column(db.String(200), nullable=False)
    refresh_token = db.Column(db.String(200), nullable=False)
    expires_at = db.Column(db.Integer, nullable=False) 
    aggregates = db.relationship('Aggregate', backref='user', lazy=True, cascade="all, delete-orphan")

class Aggregate(db.Model):
    """Aggregate model for storing Strava activity aggregates."""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_stats = db.Column(db.Text, nullable=False)
    type_stats = db.Column(db.Text, nullable=False)
    map_data = db.Column(db.Text, nullable=False)
    # *** Maybe consider using db.JSONB instead of db.Text ***
    # *** Would need: from sqalchemy.dialects.postgresql import JSONB ***