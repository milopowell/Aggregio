# Main App for Aggregio
# This file initializes the Flask application and sets up the routes.
# Project started 07-22-2024 by Milo Powell

import os
import requests
import uuid
import json
from flask import Flask, redirect, url_for, session, request, render_template, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv # Remove for Railway deployment
from datetime import datetime
from flask_migrate import Migrate

# Load environment variables from .env file
# Remove for Railway deployment
load_dotenv()

# --- App & Database Configuration ---
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')


# Database configuration
db_url = os.getenv('DATABASE_URL')
""" old code for railway deployment
    db_url = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url """
if db_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace("postgres://", "postgresql://", 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg://milo@localhost:5432/my_local_db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- Credentials & Constants ---
STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
MAPBOX_TOKEN = os.getenv('MAPBOX_TOKEN')
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_URL = "https://www.strava.com/api/v3"
SCOPE = "read,activity:read_all"

# --- Database Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    access_token = db.Column(db.String(200), nullable=False)
    aggregates = db.relationship('Aggregate', backref='user', lazy=True, cascade="all, delete-orphan")

class Aggregate(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_stats = db.Column(db.Text, nullable=False)
    type_stats = db.Column(db.Text, nullable=False)
    map_data = db.Column(db.Text, nullable=False)

# --- Helper Functions ---
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

def get_current_user():
    return db.session.get(User, session['user_id']) if 'user_id' in session else None

def get_strava_api_headers():
    user = get_current_user()
    return {'Authorization': f'Bearer {user.access_token}'} if user else None

def meters_to_miles(m): return m * 0.000621371
def meters_to_feet(m): return m * 3.28084
def seconds_to_hms(s): return f"{s//3600:02}:{(s%3600)//60:02}:{s%60:02}"
def mps_to_mph(mps): return mps * 2.23694

# --- Routes ---
@app.route('/')
def index():
    if get_current_user(): return redirect(url_for('profile'))
    auth_url = f"{STRAVA_AUTH_URL}?client_id={STRAVA_CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={SCOPE}"
    return render_template('home.html', auth_url=auth_url)

@app.route('/strava/callback')
def strava_callback():
    code = request.args.get('code')
    if not code: abort(400)
    token_data = {'client_id': STRAVA_CLIENT_ID, 'client_secret': STRAVA_CLIENT_SECRET, 'code': code, 'grant_type': 'authorization_code'}
    response = requests.post(STRAVA_TOKEN_URL, data=token_data)
    if response.status_code != 200: abort(response.status_code)
    token_info = response.json()
    user = db.session.get(User, token_info['athlete']['id'])
    if user:
        user.access_token = token_info['access_token']
    else:
        user = User(id=token_info['athlete']['id'], username=token_info['athlete']['username'], access_token=token_info['access_token'])
        db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    return redirect(url_for('profile'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    user = get_current_user()
    if not user: return redirect(url_for('index'))
    headers = get_strava_api_headers()
    athlete_response = requests.get(f"{STRAVA_API_URL}/athlete", headers=headers)
    if athlete_response.status_code != 200:
        session.clear()
        return redirect(url_for('index'))
    return render_template('profile.html', athlete=athlete_response.json())

# View Aggregates
@app.route('/aggregates')
def view_aggregates():
    user = get_current_user()
    if not user: return redirect(url_for('index'))
    user_aggregates = Aggregate.query.filter_by(user_id=user.id).order_by(Aggregate.created_at.desc()).all()
    return render_template('aggregates.html', aggregates=user_aggregates)

# Create Aggregate Start
@app.route('/aggregates/new')
def create_aggregate_start():
    if 'clear' in request.args:
        session['selected_activities'] = []
    elif 'selected_activities' not in session:
        session['selected_activities'] = []
    headers = get_strava_api_headers()
    page = request.args.get('page', 1, type=int)
    activities_response = requests.get(f"{STRAVA_API_URL}/athlete/activities", headers=headers, params={'page': page, 'per_page': 20})
    if activities_response.status_code != 200: abort(500)
    return render_template('create_aggregate.html', activities=activities_response.json(), page=page, selected_activities=session['selected_activities'], meters_to_miles=meters_to_miles)

# Update Activity Selection for Aggregate
@app.route('/aggregates/update_selection', methods=['POST'])
def update_selection():
    if not get_current_user(): abort(401)
    data = request.json
    selection_set = set(session.get('selected_activities', []))
    if data.get('selected'):
        selection_set.add(str(data.get('id')))
    else:
        selection_set.discard(str(data.get('id')))
    session['selected_activities'] = list(selection_set)
    return jsonify(count=len(session['selected_activities']))

# Create Aggregate Finalization
@app.route('/aggregates/finalize', methods=['GET', 'POST'])
def finalize_aggregate():
    user = get_current_user()
    if not user: return redirect(url_for('index'))
    activity_ids = session.get('selected_activities', [])
    if not activity_ids: return redirect(url_for('create_aggregate_start'))
    headers = get_strava_api_headers()
    if request.method == 'POST':
        aggregate_name = request.form.get('aggregate_name')
        if not aggregate_name: return redirect(url_for('finalize_aggregate'))
        total_stats, type_stats, map_data_list = {'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0, 'calories': 0, 'max_speed': 0, 'average_heartrate_sum': 0, 'heartrate_activity_count':0}, {}, []
        for act_id in activity_ids:
            act_response = requests.get(f"{STRAVA_API_URL}/activities/{act_id}", headers=headers)
            if act_response.status_code == 200:
                act_data = act_response.json()
                # Aggregate the activity data
                total_stats['distance'] += act_data.get('distance', 0)
                total_stats['moving_time'] += act_data.get('moving_time', 0)
                total_stats['total_elevation_gain'] += act_data.get('total_elevation_gain', 0)
                total_stats['calories'] += act_data.get('calories', 0)
                total_stats['max_speed'] = max(total_stats['max_speed'], act_data.get('max_speed', 0))
                # Calculate average heartrate if available
                if act_data.get('has_heartrate'):
                    total_stats['average_heartrate_sum'] += act_data.get('average_heartrate', 0)
                    total_stats['heartrate_activity_count'] += 1
                act_type = act_data.get('type', 'Unknown')
                # Update type_stats with activity type data
                if act_type not in type_stats: 
                    type_stats[act_type] = {'distance': 0, 'moving_time': 0, 'count': 0, 'calories': 0}
                type_stats[act_type]['distance'] += act_data.get('distance', 0)
                type_stats[act_type]['moving_time'] += act_data.get('moving_time', 0)
                type_stats[act_type]['count'] += 1
                type_stats[act_type]['calories'] += act_data.get('calories', 0)
                
                if act_data.get('map', {}).get('summary_polyline'):
                    map_data_list.append({"polyline": act_data['map']['summary_polyline'], "type": act_type})
        new_aggregate = Aggregate(user_id=user.id, name=aggregate_name, total_stats=json.dumps(total_stats), type_stats=json.dumps(type_stats), map_data=json.dumps(map_data_list))
        db.session.add(new_aggregate)
        db.session.commit()
        session.pop('selected_activities', None)
        return redirect(url_for('view_aggregates'))
    return render_template('finalize_aggregate.html', count=len(activity_ids))

# View Single Aggregate
@app.route('/aggregate/<aggregate_id>')
def view_single_aggregate(aggregate_id):
    user = get_current_user()
    if not user: return redirect(url_for('index'))
    aggregate = Aggregate.query.filter_by(id=aggregate_id, user_id=user.id).first_or_404()
    aggregate.total_stats = json.loads(aggregate.total_stats)
    aggregate.type_stats = json.loads(aggregate.type_stats)
    map_data = [{"decoded_line": decode_polyline(item["polyline"]), "type": item["type"]} for item in json.loads(aggregate.map_data)]
    return render_template('view_aggregate.html', aggregate=aggregate, map_data=map_data, mapbox_token=MAPBOX_TOKEN, meters_to_miles=meters_to_miles, meters_to_feet=meters_to_feet, seconds_to_hms=seconds_to_hms, mps_to_mph=mps_to_mph)

# Edit Aggregate
@app.route('/aggregate/<aggregate_id>/edit', methods=['GET', 'POST'])
def edit_aggregate(aggregate_id):
    user = get_current_user()
    if not user: return redirect(url_for('index'))
    aggregate = Aggregate.query.filter_by(id=aggregate_id, user_id=user.id).first_or_404()
    if request.method == 'POST':
        new_name = request.form.get('aggregate_name')
        if new_name:
            aggregate.name = new_name
            db.session.commit()
            return redirect(url_for('view_aggregates'))
    return render_template('edit_aggregate.html', aggregate=aggregate)

# Delete Aggregate
@app.route('/aggregate/<aggregate_id>/delete', methods=['POST'])
def delete_aggregate(aggregate_id):
    user = get_current_user()
    if not user: abort(401)
    aggregate = Aggregate.query.filter_by(id=aggregate_id, user_id=user.id).first_or_404()
    db.session.delete(aggregate)
    db.session.commit()
    return redirect(url_for('view_aggregates'))

# Activities View (TBD)***
@app.route('/activities')
def view_activities():
    user = get_current_user()
    if not user: return redirect(url_for('index'))
    headers = get_strava_api_headers()
    
    page = request.args.get('page', 1, type=int)
    per_page = 15 # You can adjust how many activities show per page
    
    # Fetch a paginated list of activities from Strava
    activities_response = requests.get(
        f"{STRAVA_API_URL}/athlete/activities", 
        headers=headers, 
        params={'page': page, 'per_page': per_page}
    )
    if activities_response.status_code != 200:
        abort(500)
    
    activities = activities_response.json()
    
    # Simple check to see if a 'Next' page button is needed
    has_next_page = len(activities) == per_page

    return render_template(
        'activities.html', 
        activities=activities, 
        page=page, 
        has_next_page=has_next_page,
        meters_to_miles=meters_to_miles,
        seconds_to_hms=seconds_to_hms
    )

# View Single Activity
@app.route('/activity/<int:activity_id>')
def view_single_activity(activity_id):
    user = get_current_user()
    if not user: return redirect(url_for('index'))
    headers = get_strava_api_headers()

    # Fetch the detailed data for one specific activity
    activity_response = requests.get(f"{STRAVA_API_URL}/activities/{activity_id}", headers=headers)
    if activity_response.status_code != 200:
        abort(activity_response.status_code)

    activity = activity_response.json()
    
    # Decode the polyline for the map, if it exists
    map_data = None
    if activity.get('map', {}).get('summary_polyline'):
        decoded_line = decode_polyline(activity['map']['summary_polyline'])
        map_data = [{"decoded_line": decoded_line, "type": activity.get('type', 'default')}]

    return render_template(
        'view_activity.html',
        activity=activity,
        map_data=map_data,
        mapbox_token=MAPBOX_TOKEN,
        meters_to_miles=meters_to_miles,
        meters_to_feet=meters_to_feet,
        seconds_to_hms=seconds_to_hms,
        mps_to_mph=mps_to_mph
    )

# Main entry point
if __name__ == '__main__':
    app.run(debug=True, port=5000)
