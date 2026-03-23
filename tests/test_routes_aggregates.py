# test_routes_aggregates.py
import json
import pytest
from unittest.mock import patch, MagicMock
from app.models import Aggregate

# Reusable fake data
FAKE_HEADERS = {'Authorization': 'Bearer fake_token'}

MOCK_ACTIVITY = {
    'id': 1,
    'name': 'Morning Run',
    'type': 'Run',
    'distance': 5000,
    'moving_time': 1800,
    'total_elevation_gain': 50,
    'calories': 300,
    'has_heartrate': False,
    'start_date_local': '2024-01-01T07:00:00Z',
    'map': {'summary_polyline': '_p~iF~ps|U_ulLnnqC_mqNvxq`@'}
}

MOCK_ACTIVITIES = [MOCK_ACTIVITY]


# View aggregates 

def test_view_aggregates_unauthenticated(client):
    response = client.get('/aggregates/')
    assert response.status_code == 302
    assert '/' in response.location

def test_view_aggregates_empty(logged_in_client):
    response = logged_in_client.get('/aggregates/')
    assert response.status_code == 200
    assert b'No Aggregates Yet' in response.data

def test_view_aggregates_shows_list(logged_in_client, sample_aggregate):
    response = logged_in_client.get('/aggregates/')
    assert response.status_code == 200
    assert b'Test Aggregate' in response.data


# Create aggregate

def test_create_aggregate_unauthenticated(client):
    response = client.get('/aggregates/new')
    assert response.status_code == 302
    assert '/' in response.location

def test_create_aggregate_authenticated(logged_in_client):
    with patch('app.aggregates.routes.get_strava_api_headers') as mock_headers:
        with patch('app.aggregates.routes.requests.get') as mock_get:
            mock_headers.return_value = FAKE_HEADERS
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = MOCK_ACTIVITIES
            response = logged_in_client.get('/aggregates/new')
            assert response.status_code == 200
            assert b'Morning Run' in response.data

def test_create_aggregate_clears_selection(logged_in_client):
    with patch('app.aggregates.routes.get_strava_api_headers') as mock_headers:
        with patch('app.aggregates.routes.requests.get') as mock_get:
            mock_headers.return_value = FAKE_HEADERS
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = MOCK_ACTIVITIES

            # Set a selection first
            with logged_in_client.session_transaction() as sess:
                sess['selected_activities'] = ['1', '2', '3']

            # Visit with clear param
            response = logged_in_client.get('/aggregates/new?clear=1')
            assert response.status_code == 200

            # Confirm selection was cleared
            with logged_in_client.session_transaction() as sess:
                assert sess.get('selected_activities') == []


# Update selection

def test_update_selection_add(logged_in_client):
    response = logged_in_client.post(
        '/aggregates/update_selection',
        data=json.dumps({'id': '123', 'selected': True}),
        content_type='application/json'
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['count'] == 1

def test_update_selection_remove(logged_in_client):
    # Add an activity first
    with logged_in_client.session_transaction() as sess:
        sess['selected_activities'] = ['123']

    # Now remove it
    response = logged_in_client.post(
        '/aggregates/update_selection',
        data=json.dumps({'id': '123', 'selected': False}),
        content_type='application/json'
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['count'] == 0

def test_update_selection_unauthenticated(client):
    response = client.post(
        '/aggregates/update_selection',
        data=json.dumps({'id': '123', 'selected': True}),
        content_type='application/json'
    )
    assert response.status_code == 401


# Finalize aggregate

def test_finalize_redirects_if_no_selection(logged_in_client):
    # Clear any existing selection
    with logged_in_client.session_transaction() as sess:
        sess['selected_activities'] = []
    response = logged_in_client.get('/aggregates/finalize')
    assert response.status_code == 302

def test_finalize_get_shows_form(logged_in_client):
    with logged_in_client.session_transaction() as sess:
        sess['selected_activities'] = ['1', '2']
    response = logged_in_client.get('/aggregates/finalize')
    assert response.status_code == 200
    assert b'Name Your Aggregate' in response.data

def test_finalize_post_creates_aggregate(logged_in_client, db_session, sample_user):
    with logged_in_client.session_transaction() as sess:
        sess['selected_activities'] = ['1']

    with patch('app.aggregates.routes.get_strava_api_headers') as mock_headers:
        with patch('app.aggregates.routes.fetch_activity') as mock_fetch:
            mock_headers.return_value = FAKE_HEADERS
            mock_fetch.return_value = ('1', MOCK_ACTIVITY)

            # Patch ThreadPoolExecutor to run synchronously
            with patch('app.aggregates.routes.ThreadPoolExecutor') as mock_executor:
                mock_cm = MagicMock()
                mock_executor.return_value.__enter__ = MagicMock(return_value=mock_cm)
                mock_executor.return_value.__exit__ = MagicMock(return_value=False)
                mock_future = MagicMock()
                mock_future.result.return_value = ('1', MOCK_ACTIVITY)
                mock_cm.submit.return_value = mock_future

                with patch('app.aggregates.routes.as_completed') as mock_as_completed:
                    mock_as_completed.return_value = [mock_future]

                    response = logged_in_client.post(
                        '/aggregates/finalize',
                        data={'aggregate_name': 'My New Aggregate'}
                    )

    assert response.status_code == 302
    assert '/aggregates/' in response.location

    # Confirm it was saved to the database
    agg = Aggregate.query.filter_by(
        user_id=sample_user.id,
        name='My New Aggregate'
    ).first()
    assert agg is not None

def test_finalize_post_no_name_redirects(logged_in_client):
    with logged_in_client.session_transaction() as sess:
        sess['selected_activities'] = ['1']
    response = logged_in_client.post(
        '/aggregates/finalize',
        data={'aggregate_name': ''}
    )
    assert response.status_code == 302


# View single aggregate

def test_view_single_aggregate_success(logged_in_client, sample_aggregate):
    response = logged_in_client.get(f'/aggregates/{sample_aggregate.id}')
    assert response.status_code == 200
    assert b'Test Aggregate' in response.data

def test_view_single_aggregate_wrong_user(client, db_session, sample_aggregate, other_user):
    with client.session_transaction() as sess:
        sess['user_id'] = other_user.id
    response = client.get(f'/aggregates/{sample_aggregate.id}')
    assert response.status_code == 404

def test_view_single_aggregate_not_found(logged_in_client):
    response = logged_in_client.get('/aggregates/nonexistent-uuid-1234')
    assert response.status_code == 404


# Edit aggregate

def test_edit_aggregate_get(logged_in_client, sample_aggregate):
    response = logged_in_client.get(f'/aggregates/{sample_aggregate.id}/edit')
    assert response.status_code == 200
    assert b'Test Aggregate' in response.data

def test_edit_aggregate_post_updates_name(logged_in_client, sample_aggregate, db_session):
    response = logged_in_client.post(
        f'/aggregates/{sample_aggregate.id}/edit',
        data={'aggregate_name': 'Renamed Aggregate'}
    )
    assert response.status_code == 302

    # Confirm name was updated in the database
    updated = db_session.get(Aggregate, sample_aggregate.id)
    assert updated.name == 'Renamed Aggregate'

def test_edit_aggregate_wrong_user(client, sample_aggregate, other_user):
    with client.session_transaction() as sess:
        sess['user_id'] = other_user.id
    response = client.post(
        f'/aggregates/{sample_aggregate.id}/edit',
        data={'aggregate_name': 'Hacked Name'}
    )
    assert response.status_code == 404


# Delete aggregate

def test_delete_aggregate_success(logged_in_client, sample_aggregate, db_session):
    agg_id = sample_aggregate.id
    response = logged_in_client.post(f'/aggregates/{agg_id}/delete')
    assert response.status_code == 302
    assert '/aggregates/' in response.location

    # Confirm it's gone from the database
    assert db_session.get(Aggregate, agg_id) is None

def test_delete_aggregate_wrong_user(client, sample_aggregate, db_session, other_user):
    with client.session_transaction() as sess:
        sess['user_id'] = other_user.id
    response = client.post(f'/aggregates/{sample_aggregate.id}/delete')
    assert response.status_code == 404

    # Confirm it was not deleted
    assert db_session.get(Aggregate, sample_aggregate.id) is not None

def test_delete_aggregate_unauthenticated(client, sample_aggregate):
    response = client.post(f'/aggregates/{sample_aggregate.id}/delete')
    assert response.status_code == 401 