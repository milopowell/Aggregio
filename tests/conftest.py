# Pytest config
import pytest
from app import create_app, db as _db
from app.models import User, Aggregate

# Test config 
# Points to in-memory SQLite db
class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    STRAVA_CLIENT_ID = 'fake-id'
    STRAVA_CLIENT_SECRET = 'fake-secret'
    REDIRECT_URI = 'http://localhost/strava/callback'
    MAPBOX_TOKEN = 'fake-mapbox-token'
    STRAVA_AUTH_URL = 'https://www.strava.com/oauth/authorize'
    STRAVA_TOKEN_URL = 'https://www.strava.com/oauth/token'
    STRAVA_API_URL = 'https://www.strava.com/api/v3'
    SCOPE = 'read,activity:read_all'
    DATABASE_URL = 'sqlite:///:memory:'

# App fixture
# Creates a test Flask app once per session
@pytest.fixture(scope='session')
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()       # Create all tables in the in-memory DB
        yield app              # Hand the app to the test
        _db.drop_all()         # Tear down all tables when done


# Client fixture
# A fake browser that can make GET and POST requests
@pytest.fixture
def client(app):
    return app.test_client()


# DB session fixture
# Provides a clean DB session and rolls back after each test
@pytest.fixture
def db_session(app):
    with app.app_context():
        yield _db.session
        _db.session.rollback()


# Sample user fixture
# A pre-built user with a fake strava token that hasn't expired
@pytest.fixture
def sample_user(db_session):
    user = User(
        id=12345,
        username='testuser',
        access_token='fake_access_token',
        refresh_token='fake_refresh_token',
        expires_at=9999999999    # Far future — token never expires in tests
    )
    db_session.add(user)
    db_session.commit()
    yield user
    if db_session.get(User, 12345):
        db_session.delete(user)
        db_session.commit()


# Logged-in client fixture
# A fake browser that already has a user_id in the session
@pytest.fixture
def logged_in_client(client, sample_user):
    with client.session_transaction() as sess:
        sess['user_id'] = sample_user.id
    return client


# Sample aggregate fixture
# A pre-built Aggregate owned by the sample user
@pytest.fixture
def sample_aggregate(db_session, sample_user):
    import json
    agg = Aggregate(
        user_id=sample_user.id,
        name='Test Aggregate',
        total_stats=json.dumps({
            'distance': 16093,
            'moving_time': 3600,
            'total_elevation_gain': 200,
            'calories': 500,
            'max_speed': 4.0,
            'average_heartrate_sum': 0,
            'heartrate_activity_count': 0
        }),
        type_stats=json.dumps({
            'Run': {'distance': 16093, 'moving_time': 3600, 'count': 2, 'calories': 500}
        }),
        map_data=json.dumps([])
    )
    db_session.add(agg)
    db_session.commit()
    yield agg
    db_session.delete(agg)
    db_session.commit()