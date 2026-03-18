# All routes starting with '/aggregates' 
import json
import requests
from flask import Blueprint, redirect, url_for, session, request, render_template, abort, jsonify, current_app
from concurrent.futures import ThreadPoolExecutor, as_completed
from .. import db
from ..models import Aggregate
from ..helpers import (
    get_current_user, get_strava_api_headers, decode_polyline, 
    meters_to_miles, meters_to_feet, seconds_to_hms, mps_to_mph,
    accumulate_stats, fetch_activity
)
aggregates_bp = Blueprint('aggregates', __name__, template_folder='templates')

@aggregates_bp.route('/')
def view_aggregates():
    user = get_current_user()
    if not user:
        return redirect(url_for('main.index'))
    user_aggregates = Aggregate.query.filter_by(user_id=user.id).order_by(Aggregate.created_at.desc()).all()
    return render_template('aggregates/aggregates.html', aggregates=user_aggregates)

@aggregates_bp.route('/new')
def create_aggregate_start():
    user = get_current_user()
    if not user:
        return redirect(url_for('main.index'))
        
    if 'clear' in request.args:
        session['selected_activities'] = []
    elif 'selected_activities' not in session:
        session['selected_activities'] = []
    
    headers = get_strava_api_headers()
    page = request.args.get('page', 1, type=int)
    activities_response = requests.get(
        f"{current_app.config['STRAVA_API_URL']}/athlete/activities",
        headers=headers, params={'page': page, 'per_page': 20}
    )
    if activities_response.status_code != 200:
        abort(500)
        
    return render_template('aggregates/create_aggregate.html',
        activities=activities_response.json(), page=page,
        selected_activities=session['selected_activities'],
        meters_to_miles=meters_to_miles)

@aggregates_bp.route('/update_selection', methods=['POST'])
def update_selection():
    if not get_current_user():
        abort(401)
    data = request.json
    selection_set = set(session.get('selected_activities', []))
    if data.get('selected'):
        selection_set.add(str(data.get('id')))
    else:
        selection_set.discard(str(data.get('id')))
    session['selected_activities'] = list(selection_set)
    return jsonify(count=len(session['selected_activities']))

@aggregates_bp.route('/finalize', methods=['GET', 'POST'])
def finalize_aggregate():
    user = get_current_user()
    if not user:
        return redirect(url_for('main.index'))

    activity_ids = session.get('selected_activities', [])
    if not activity_ids:
        return redirect(url_for('aggregates.create_aggregate_start'))

    headers = get_strava_api_headers()
    if request.method == 'POST':
        aggregate_name = request.form.get('aggregate_name')
        if not aggregate_name:
            return redirect(url_for('aggregates.finalize_aggregate'))

        headers = get_strava_api_headers()
        api_url = current_app.config['STRAVA_API_URL']

        total_stats = {
            'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0,
            'calories': 0, 'max_speed': 0, 'average_heartrate_sum': 0,
            'heartrate_activity_count': 0
        }
        type_stats, map_data_list = {}, []
        rate_limited = False

        # Fetch all activities concurrently — max 5 workers to respect Strava rate limits
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(fetch_activity, act_id, headers, api_url): act_id
                for act_id in activity_ids
            }
            for future in as_completed(futures):
                act_id, act_data = future.result()
                if act_data is None:
                    continue
                if act_data.get('_error') == 'rate_limited':
                    rate_limited = True
                    continue
                accumulate_stats(total_stats, type_stats, map_data_list, act_data)

        if rate_limited:
            # Surface this to the user rather than silently dropping activities
            return render_template(
                'aggregates/finalize_aggregate.html',
                count=len(activity_ids),
                error="Strava rate limit reached. Please wait a moment and try again."
            )

        new_aggregate = Aggregate(
            user_id=user.id,
            name=aggregate_name,
            total_stats=json.dumps(total_stats),
            type_stats=json.dumps(type_stats),
            map_data=json.dumps(map_data_list)
        )
        db.session.add(new_aggregate)
        db.session.commit()
        session.pop('selected_activities', None)
        return redirect(url_for('aggregates.view_aggregates'))
        
    return render_template('aggregates/finalize_aggregate.html', count=len(activity_ids))

@aggregates_bp.route('/<string:aggregate_id>')
def view_single_aggregate(aggregate_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('main.index'))
    aggregate = Aggregate.query.filter_by(id=aggregate_id, user_id=user.id).first_or_404()
    aggregate.total_stats = json.loads(aggregate.total_stats)
    aggregate.type_stats = json.loads(aggregate.type_stats)
    map_data = [{"decoded_line": decode_polyline(item["polyline"]), "type": item["type"]} for item in json.loads(aggregate.map_data)]
    # Default to showing pace
    display_mode = 'pace'
    activity_types = list(aggregate.type_stats.keys())
    # If statement if there is only one activity type AND it's 'ride' show speed
    # *** Put into 'helper.py later ***
    if len(activity_types) == 1 and activity_types[0] == 'Ride':
        display_mode = 'speed'
    elif len(activity_types) == 1 and activity_types[0] == 'Swim': 
        display_mode = 'yards'
    return render_template('aggregates/view_aggregate.html',
        aggregate=aggregate,
        map_data=map_data,
        mapbox_token=current_app.config['MAPBOX_TOKEN'],
        meters_to_miles=meters_to_miles, 
        meters_to_feet=meters_to_feet, 
        seconds_to_hms=seconds_to_hms,
        mps_to_mph=mps_to_mph,
        display_mode=display_mode
    
    )

@aggregates_bp.route('/<string:aggregate_id>/edit', methods=['GET', 'POST'])
def edit_aggregate(aggregate_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('main.index'))
    aggregate = Aggregate.query.filter_by(id=aggregate_id, user_id=user.id).first_or_404()
    if request.method == 'POST':
        new_name = request.form.get('aggregate_name')
        if new_name:
            aggregate.name = new_name
            db.session.commit()
            return redirect(url_for('aggregates.view_aggregates'))
    return render_template('aggregates/edit_aggregate.html', aggregate=aggregate)

@aggregates_bp.route('/<string:aggregate_id>/delete', methods=['POST'])
def delete_aggregate(aggregate_id):
    user = get_current_user()
    if not user:
        abort(401)
    aggregate = Aggregate.query.filter_by(id=aggregate_id, user_id=user.id).first_or_404()
    db.session.delete(aggregate)
    db.session.commit()
    return redirect(url_for('aggregates.view_aggregates'))