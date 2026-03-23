# Test helpers
import pytest
from app.helpers import (
    decode_polyline,
    seconds_to_hms,
    get_pace,
    get_pace_per_100y,
    meters_to_miles,
    meters_to_feet,
    mps_to_mph,
    accumulate_stats
)

# -- Decode polyline

def test_decode_polyline_valid():
    # Known polyline string with expected coordinates
    result = decode_polyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@')
    assert len(result) == 3
    assert isinstance(result[0], tuple)

def test_decode_polyline_none():
    assert decode_polyline(None) == []

def test_decode_polyline_empty():
    assert decode_polyline('') == []

def test_decode_polyline_invalid():
    assert decode_polyline('invalid') == []


# -- seconds_to_hms

def test_seconds_to_hms_normal():
    assert seconds_to_hms(3661) == '01:01:01'

def test_seconds_to_hms_zero():
    assert seconds_to_hms(0) == '00:00:00'

def test_seconds_to_hms_none():
    assert seconds_to_hms(None) == '00:00:00'

def test_seconds_to_hms_one_hour():
    assert seconds_to_hms(3600) == '01:00:00'


# -- get_pace

def test_get_pace_normal():
    # 1 mile in 8 minutes = 1609m in 480 seconds
    result = get_pace(480, 1609)
    assert result == '8:00'  

def test_get_pace_zero_distance():
    assert get_pace(480, 0) == 'N/A'

def test_get_pace_zero_time():
    assert get_pace(0, 1609) == 'N/A'

def test_get_pace_none_inputs():
    assert get_pace(None, None) == 'N/A'


# -- get_pace_per_100y

def test_get_pace_per_100y_normal():
    result = get_pace_per_100y(600, 1000)
    assert isinstance(result, str)
    assert ':' in result

def test_get_pace_per_100y_zero_distance():
    assert get_pace_per_100y(600, 0) == 'N/A'

def test_get_pace_per_100y_none():
    assert get_pace_per_100y(None, None) == 'N/A'


# -- unit conversions

def test_meters_to_miles():
    assert abs(meters_to_miles(1609.34) - 1.0) < 0.01

def test_meters_to_feet():
    assert abs(meters_to_feet(1) - 3.28084) < 0.001

def test_mps_to_mph():
    assert abs(mps_to_mph(1) - 2.23694) < 0.001


# -- accumulate_stats

def test_accumulate_stats_basic():
    total = {
        'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0,
        'calories': 0, 'max_speed': 0, 'average_heartrate_sum': 0,
        'heartrate_activity_count': 0
    }
    types, maps = {}, []
    act = {
        'distance': 5000, 'moving_time': 1800, 'total_elevation_gain': 50,
        'calories': 300, 'type': 'Run', 'has_heartrate': False,
        'map': {'summary_polyline': '_p~iF~ps|U_ulLnnqC_mqNvxq`@'}
    }
    accumulate_stats(total, types, maps, act)

    assert total['distance'] == 5000
    assert total['moving_time'] == 1800
    assert types['Run']['count'] == 1
    assert types['Run']['calories'] == 300
    assert len(maps) == 1

def test_accumulate_stats_heartrate():
    total = {
        'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0,
        'calories': 0, 'max_speed': 0, 'average_heartrate_sum': 0,
        'heartrate_activity_count': 0
    }
    act = {
        'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0,
        'calories': 0, 'type': 'Run', 'has_heartrate': True,
        'average_heartrate': 155, 'map': {}
    }
    accumulate_stats(total, {}, [], act)

    assert total['average_heartrate_sum'] == 155
    assert total['heartrate_activity_count'] == 1

def test_accumulate_stats_no_polyline():
    maps = []
    act = {
        'distance': 1000, 'moving_time': 300, 'total_elevation_gain': 0,
        'calories': 0, 'type': 'Run', 'has_heartrate': False,
        'map': {}    # No polyline
    }
    accumulate_stats({
        'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0,
        'calories': 0, 'max_speed': 0, 'average_heartrate_sum': 0,
        'heartrate_activity_count': 0
    }, {}, maps, act)

    assert len(maps) == 0

def test_accumulate_stats_multiple_activities():
    total = {
        'distance': 0, 'moving_time': 0, 'total_elevation_gain': 0,
        'calories': 0, 'max_speed': 0, 'average_heartrate_sum': 0,
        'heartrate_activity_count': 0
    }
    types, maps = {}, []
    for _ in range(3):
        accumulate_stats(total, types, maps, {
            'distance': 1000, 'moving_time': 300, 'total_elevation_gain': 10,
            'calories': 100, 'type': 'Run', 'has_heartrate': False, 'map': {}
        })

    assert total['distance'] == 3000
    assert types['Run']['count'] == 3
