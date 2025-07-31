# Routes for '/', '/profile', and '/logout'
import requests
from flask import Blueprint, redirect, url_for, session, request, render_template, abort, current_app
from .. import db
from ..models import User
from ..helpers import get_strava_api_headers, get_current_user

main_bp = Blueprint('main', __name__, template_folder='templates')

@main_bp.route('/')
def index():
    if get_current_user():
        return redirect(url_for('main.profile'))

    auth_url = (
        f"{current_app.config['STRAVA_AUTH_URL']}?"
        f"client_id={current_app.config['STRAVA_CLIENT_ID']}&"
        f"redirect_uri={current_app.config['REDIRECT_URI']}&"
        f"response_type=code&scope={current_app.config['SCOPE']}"
    )
    return render_template('main/home.html', auth_url=auth_url)

@main_bp.route('/strava/callback')
def strava_callback():
    code = request.args.get('code')
    if not code:
        abort(400)

    token_data = {
        'client_id': current_app.config['STRAVA_CLIENT_ID'],
        'client_secret': current_app.config['STRAVA_CLIENT_SECRET'],
        'code': code,
        'grant_type': 'authorization_code'
    }
    response = requests.post(current_app.config['STRAVA_TOKEN_URL'], data=token_data)
    if response.status_code != 200:
        abort(response.status_code)

    token_info = response.json()
    user = db.session.get(User, token_info['athlete']['id'])
    if not user:
        user = User(id=token_info['athlete']['id'], username=token_info['athlete']['username'])
        db.session.add(user)

    user.access_token = token_info['access_token']
    user.refresh_token = token_info['refresh_token']
    user.expires_at = token_info['expires_at']
    db.session.commit()

    session['user_id'] = user.id
    return redirect(url_for('main.profile'))

@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))

@main_bp.route('/profile')
def profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('main.index'))

    headers = get_strava_api_headers()
    athlete_response = requests.get(f"{current_app.config['STRAVA_API_URL']}/athlete", headers=headers)
    if athlete_response.status_code != 200:
        session.clear()
        return redirect(url_for('main.index'))

    return render_template('main/profile.html', athlete=athlete_response.json())
