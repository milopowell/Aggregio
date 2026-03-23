# test_models
import json
import pytest
from app.models import User, Aggregate

# User model

def test_user_creation(db_session, sample_user):
    # Confirm user was saved and can be retrieved
    fetched = db_session.get(User, 12345)
    assert fetched is not None
    assert fetched.username == 'testuser'
    assert fetched.access_token == 'fake_access_token'

def test_user_has_no_aggregates_by_default(db_session, sample_user):
    fetched = db_session.get(User, 12345)
    assert fetched.aggregates == []

def test_user_aggregate_relationship(db_session, sample_user, sample_aggregate):
    fetched = db_session.get(User, 12345)
    assert len(fetched.aggregates) == 1
    assert fetched.aggregates[0].name == 'Test Aggregate'

def test_user_cascade_delete(db_session, sample_user):
    # Create an aggregate linked to the user
    agg = Aggregate(
        user_id=sample_user.id,
        name='To Be Deleted',
        total_stats=json.dumps({'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0,
                                'calories': 0, 'max_speed': 0, 'average_heartrate_sum': 0,
                                'heartrate_activity_count': 0}),
        type_stats=json.dumps({}),
        map_data=json.dumps([])
    )
    db_session.add(agg)
    db_session.commit()
    agg_id = agg.id

    # Delete the user
    db_session.delete(sample_user)
    db_session.commit()

    # Confirm the aggregate was also deleted
    assert db_session.get(Aggregate, agg_id) is None

    # Confirm user is deleted
    assert db_session.get(User, 12345) is None

# Aggregate Model

def test_aggregate_creation(db_session, sample_aggregate):
    fetched = db_session.get(Aggregate, sample_aggregate.id)
    assert fetched is not None
    assert fetched.name == 'Test Aggregate'
    assert fetched.user_id == 12345

def test_aggregate_id_is_uuid(db_session, sample_aggregate):
    # UUID format: 8-4-4-4-12 hex characters
    parts = sample_aggregate.id.split('-')
    assert len(parts) == 5

def test_aggregate_stats_are_valid_json(db_session, sample_aggregate):
    fetched = db_session.get(Aggregate, sample_aggregate.id)
    total = json.loads(fetched.total_stats)
    types = json.loads(fetched.type_stats)
    maps = json.loads(fetched.map_data)

    assert 'distance' in total
    assert 'Run' in types
    assert isinstance(maps, list)

def test_aggregate_created_as_is_set(db_session, sample_aggregate):
    fetched = db_session.get(Aggregate, sample_aggregate.id)
    assert fetched.created_at is not None

def test_aggregate_belongs_to_user(db_session, sample_aggregate):
    fetched = db_session.get(Aggregate, sample_aggregate.id)
    assert fetched.user is not None
    assert fetched.user.username == 'testuser'

def test_aggregate_name_update(db_session, sample_aggregate):
    sample_aggregate.name = 'Updated Name'
    db_session.commit()

    fetched = db_session.get(Aggregate, sample_aggregate.id)
    assert fetched.name == 'Updated Name'


