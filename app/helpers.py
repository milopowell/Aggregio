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
    if not user:
        return None

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

    return {'Authorization': f'Bearer {user.access_token}'}


# --- Polyline Decoder ---
def decode_polyline(polyline_str):
    if not polyline_str:
        return []
    try:
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
    except (IndexError, ValueError, TypeError):
        return []

# --- Unit Conversion Helpers ---
def meters_to_miles(m): return m * 0.000621371
def meters_to_feet(m): return m * 3.28084
def seconds_to_hms(s): 
    # Error handling for None or non-numeric input
    if not s:
        return "00:00:00"
    s = int(s)
    return f"{s//3600:02}:{(s%3600)//60:02}:{s%60:02}"
def mps_to_mph(mps): return mps * 2.23694
def get_pace(moving_time_seconds, distance_meters):
    """Calculates pace in minutes and seconds per mile"""
    # Error handling for None values
    if not moving_time_seconds or not distance_meters:
        return "N/A"
    # Error handling for zero values to avoid division by zero
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
    # Error handling for None values
    if not moving_time_seconds or not distance_meters:
        return "N/A"
    # Error handling for zero values
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

# --- Logic Testing for Aggregates ---

# Process a single activity's data into the running totals
def accumulate_stats(total_stats, type_stats, map_data_list, act_data):
    total_stats['distance'] += act_data.get('distance', 0)
    total_stats['moving_time'] += act_data.get('moving_time', 0)
    total_stats['total_elevation_gain'] += act_data.get('total_elevation_gain', 0)
    total_stats['calories'] += act_data.get('calories', 0)

    if act_data.get('has_heartrate'):
        total_stats['average_heartrate_sum'] += act_data.get('average_heartrate', 0)
        total_stats['heartrate_activity_count'] += 1

    act_type = act_data.get('type', 'Unknown')
    if act_type not in type_stats:
        type_stats[act_type] = {'distance': 0, 'moving_time': 0, 'count': 0, 'calories': 0}
    type_stats[act_type]['distance'] += act_data.get('distance', 0)
    type_stats[act_type]['moving_time'] += act_data.get('moving_time', 0)
    type_stats[act_type]['count'] += 1
    type_stats[act_type]['calories'] += act_data.get('calories', 0)

    if act_data.get('map', {}).get('summary_polyline'):
        map_data_list.append({
            "polyline": act_data['map']['summary_polyline'],
            "type": act_type
        })

# Fetch a single activity from Strava. Returns (act_id, data) or (act_id, None)
def fetch_activity(act_id, headers, api_url):
    try:
        response = requests.get(
            f"{api_url}/activities/{act_id}",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            return act_id, response.json()
        elif response.status_code == 429:
            return act_id, {'_error': 'rate_limited'}
        else:
            return act_id, None
    except requests.RequestException:
        return act_id, None

