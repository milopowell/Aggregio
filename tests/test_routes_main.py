# test_routes_main.py
import pytest
from unittest.mock import patch
from app.models import User

# Reuseable fake Strava responses
MOCK_ATHLETE = {
    'id': 12345,
    'firstname': 'Test',
    'lastname': 'User',
    'username': 'testuser',
    'profile': 'https://fake-profile-pic.com/photo.jpg'
}

MOCK_TOKEN_RESPONSE = {
    'access_token': 'new_access_token',
    'refresh_token': 'new_refresh_token',
    'expires_at': 9999999999,
    'athlete': {
        'id': 99999,
        'username': 'newuser'
    }
}

# Index Routes

def test_index_unauthenticated_shows_login(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'Connect with Strava' in response.data

def test_index_authenticated_redirects_to_profile(logged_in_client):
    with patch('app.main.routes.requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = MOCK_ATHLETE
        response = logged_in_client.get('/')
        assert response.status_code == 302
        assert '/profile' in response.location

# Profile route

def test_profile_authenticated_renders(logged_in_client):
    with patch('app.main.routes.requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = MOCK_ATHLETE
        response = logged_in_client.get('/profile')
        assert response.status_code == 200
        assert b'Test' in response.data

def test_profile_unauthenticated_redirects(client):
    response = client.get('/profile')
    assert response.status_code == 302
    assert '/' in response.location

def test_profile_bad_strava_token_clears_session(logged_in_client):
    with patch('app.main.routes.requests.get') as mock_get:
        # Simulate strava rejecting the token
        mock_get.return_value.status_code = 401
        response = logged_in_client.get('/profile')
        assert response.status_code == 302
        # Confirm session was cleared by checking we're redirected to index
        assert '/' in response.location

        # Confirm a subsequent request hits the login page not profile
        follow_response = logged_in_client.get('/')
        assert b'Connect with Strava' in follow_response.data

# Logout Route

def test_logout_clears_session_and_redirects(logged_in_client):
    response = logged_in_client.get('/logout')
    assert response.status_code == 302
    assert '/' in response.location

    # Confirm session is cleared - next request should hit login page
    follow_response = logged_in_client.get('/')
    assert b'Connect with Strava' in follow_response.data

# Strava callback route

def test_strava_callback_no_code_return_400(client):
    response = client.get('/strava/callback')
    assert response.status_code == 400

def test_strava_callback_creates_new_user(client, db_session):
    with patch('app.main.routes.requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = MOCK_TOKEN_RESPONSE

        response = client.get('/strava/callback?code=fake_auth_code')
        assert response.status_code == 302
        assert '/profile' in response.location

        # Confirm user was created in the database
        user = db_session.get(User, 99999)
        assert user is not None
        assert user.username == 'newuser'
        assert user.access_token == 'new_access_token'

def test_strava_callback_updates_existing_user(client, db_session, sample_user):
    with patch('app.main.routes.requests.post') as mock_post:
        # Return token for the existing sample_user (id=12345)
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'access_token': 'updated_token',
            'refresh_token': 'updated_refresh',
            'expires_at': 9999999999,
            'athlete': {'id': 12345,'username': 'testuser' }
        }
        response = client.get('/strava/callback?code=fake_auth_code')
        assert response.status_code == 302

        # confirm token was not duplicated
        user = db_session.get(User, 12345)
        assert user.access_token == 'updated_token'

def test_strava_callback_bad_strava_response(client):
     with patch('app.main.routes.requests.post') as mock_post:
        mock_post.return_value.status_code = 400
        response = client.get('/strava/callback?code=fake_auth_code')
        assert response.status_code == 400