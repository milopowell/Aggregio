import time
import requests
from flask import session, current_app
from . import db
from .models import User

# --- User & API Helper Functions ---

def get_current_user():
    """Retrieve the current user from the session."""
    return db.session.get(User, session['user_id']) if 'user_id' in session else None

def get_strava_api_headers():
    """Get headers for Strava API requests."""
    user = get_current_user()
    return {'Authorization': f'Bearer {user.access_token}'} if user else None

    #Check if the access token is still valid
    if time.time() > user.expires_at:
        # If expired, refresh the token
        token_data = {
            'client_id': current_app.config['STRAVA_CLIENT_ID'],
            'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
            'refresh_token': user.refresh_token,
            'grant_type': 'refresh_token'
        }
        response = requests.post(current_app.config['STRAVA_TOKEN_URL'], data=token_data)
        if response.status_code != 200:
            session.clear()
            return None
        
        new_token_info = response.json()
        user.access_token = new_token_info['access_token']
        user.refresh_token = new_token_info['refresh_token']
        user.expires_at = new_token_info['expires_at']
        db.session.commit()

    return {'Authorization': f'Bearer {user.access_token}'} if user else None

# --- Polyline Decoder ---
def decode_polyline(polyline_str):
    index, lat, lng, coordinates = 0, 0, 0, []
    changes = {'latitude': 0, 'longitude': 0}
    while index < len(polyline_str):
        for unit in ['latitude', 'longitude']:
            shift, result = 0, 0
            while True:
                byte = ord(polyline_str[index]) - 63
                index += 1
                result |= (byte & 0x1f) << shift
                shift += 5
                if not byte >= 0x20: break
            changes[unit] = ~(result >> 1) if result & 1 else (result >> 1)
        lat += changes['latitude']
        lng += changes['longitude']
        coordinates.append((lat / 100000.0, lng / 100000.0))
    return coordinates

# --- Unit Conversion Helpers ---
def meters_to_miles(m): return m * 0.000621371
def meters_to_feet(m): return m * 3.28084
def seconds_to_hms(s): return f"{s//3600:02}:{(s%3600)//60:02}:{s%60:02}"
def mps_to_mph(mps): return mps * 2.23694
def get_pace(moving_time_seconds, distance_meters):
    """Calculates pace in minutes and seconds per mile"""
    if distance_meters == 0 or moving_time_seconds == 0:
        return "N/A"
    #convert meters to miles
    miles = distance_meters * 0.000621371
    if miles == 0:
        return "N/A"
    
    seconds_per_mile = moving_time_seconds / miles

    minutes = int(seconds_per_mile // 60)
    seconds = int(seconds_per_mile % 60)

    return f"{minutes:01d}:{seconds:02d}"
def get_pace_per_100y(moving_time_seconds, distance_meters):
    """Calculates pace in minutes and seconds per 100 yards"""
    if distance_meters == 0 or moving_time_seconds == 0:
        return "N/A"
    #convert meters to yards
    yards = distance_meters * 1.09361
    if yards == 0:
        return "N/A"
    
    seconds_per_100y = moving_time_seconds / (yards / 100)

    minutes = int(seconds_per_100y // 60)
    seconds = int(seconds_per_100y % 60)

    return f"{minutes:01d}:{seconds:02d}"

