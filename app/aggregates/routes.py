# All routes starting with '/aggregates'
import json
import requests
from flask import Blueprint, redirect, url_for, session, request, render_template, abort, jsonify, current_app
from .. import db
from ..models import Aggregate
from ..helpers import get_current_user, get_strava_api_headers, decode_polyline, meters_to_miles, meters_to_feet, seconds_to_hms, mps_to_mph

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

        # Collect stats for the selected activities
        total_stats, type_stats, map_data_list = {'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0, 'calories': 0, 'max_speed': 0, 'average_heartrate_sum': 0, 'heartrate_activity_count':0}, {}, []
        for act_id in activity_ids:
            act_response = requests.get(f"{current_app.config['STRAVA_API_URL']}/activities/{act_id}", headers=headers)
            if act_response.status_code == 200:
                act_data = act_response.json()
                total_stats['distance'] += act_data.get('distance', 0)
                total_stats['moving_time'] += act_data.get('moving_time', 0)
                total_stats['total_elevation_gain'] += act_data.get('total_elevation_gain', 0)
                total_stats['calories'] += act_data.get('calories', 0)
                act_type = act_data.get('type', 'Unknown')
                if act_type not in type_stats:
                    type_stats[act_type] = {'distance': 0, 'moving_time': 0, 'count': 0,'calories': 0}
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
    if len(activity_types) == 1 and activity_types[0] == 'Ride':
        display_mode = 'speed'
    return render_template('aggregates/view_aggregate.html',
        aggregate=aggregate, 
        map_data=map_data,
        mapbox_token=current_app.config['MAPBOX_TOKEN'],
        meters_to_miles=meters_to_miles, 
        meters_to_feet=meters_to_feet, 
        seconds_to_hms=seconds_to_hms,
        mps_to_mph=mps_to_mph
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