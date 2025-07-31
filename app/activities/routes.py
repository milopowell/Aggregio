# Routes for '/activities' and 'activity/<id>'

import requests
from flask import Blueprint, redirect, url_for, request, render_template, abort, current_app
from ..helpers import get_current_user, get_strava_api_headers, decode_polyline, meters_to_miles, meters_to_feet, seconds_to_hms, mps_to_mph

activities_bp = Blueprint('activities', __name__, template_folder='templates')

@activities_bp.route('/')
def view_activities():
    user = get_current_user()
    if not user:
        return redirect(url_for('main.index'))

    headers = get_strava_api_headers()
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    activities_response = requests.get(
        f"{current_app.config['STRAVA_API_URL']}/athlete/activities",
        headers=headers,
        params={'page': page, 'per_page': per_page}
    )
    if activities_response.status_code != 200:
        abort(500)
    
    activities = activities_response.json()
    has_next_page = len(activities) == per_page

    return render_template(
        'activities/activities.html',
        activities=activities,
        page=page,
        has_next_page=has_next_page,
        meters_to_miles=meters_to_miles,
        seconds_to_hms=seconds_to_hms
    )

@activities_bp.route('/<int:activity_id>')
def view_single_activity(activity_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('main.index'))

    headers = get_strava_api_headers()
    activity_response = requests.get(
        f"{current_app.config['STRAVA_API_URL']}/activities/{activity_id}",
        headers=headers
    )
    if activity_response.status_code != 200:
        abort(activity_response.status_code)

    activity = activity_response.json()
    map_data = None
    if activity.get('map', {}).get('summary_polyline'):
        decoded_line = decode_polyline(activity['map']['summary_polyline'])
        map_data = [{"decoded_line": decoded_line, "type": activity.get('type', 'default')}]

    return render_template(
        'activities/view_activity.html',
        activity=activity, map_data=map_data,
        mapbox_token=current_app.config['MAPBOX_TOKEN'],
        meters_to_miles=meters_to_miles, meters_to_feet=meters_to_feet,
        seconds_to_hms=seconds_to_hms, mps_to_mph=mps_to_mph
    )