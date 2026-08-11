"""Blue force sensor and interceptor logic."""

import numpy as np
import pytest

from msim.blue_units import BlueTEL, CommandControlUnit, RadarUnit, SatelliteUnit
from msim.red_units import RedTEL
from msim.units import nm_to_m


# ---------------------------------------------------------------------
# Sensors
# ---------------------------------------------------------------------

def test_radar_in_range():
    radar = RadarUnit("R", position=(0.0, 0.0), detection_range=10.0)
    assert radar.in_range(nm_to_m(np.array([5.0, 0.0])))
    assert not radar.in_range(nm_to_m(np.array([11.0, 0.0])))


def test_radar_in_range_none_position_is_false():
    radar = RadarUnit("R", position=(0.0, 0.0), detection_range=10.0)
    assert not radar.in_range(None)


def test_satellite_sees_anything_active_regardless_of_distance():
    sat = SatelliteUnit("S", position=(0.0, 1000.0))
    assert sat.in_range(nm_to_m(np.array([100000.0, 0.0])))
    assert not sat.in_range(None)


def test_fire_control_quality_flags():
    assert RadarUnit.fire_control_quality is True
    assert SatelliteUnit.fire_control_quality is False


# ---------------------------------------------------------------------
# CommandControlUnit: two-tier cue (any sensor) vs track (fire-control only)
# ---------------------------------------------------------------------

def test_c2_cue_fires_from_satellite_but_track_waits_for_radar():
    radar = RadarUnit("R", position=(50.0, 0.0), detection_range=5.0)  # short range
    sat = SatelliteUnit("S", position=(0.0, 30.0))  # sees everything instantly
    c2 = CommandControlUnit("C2", position=(50.0, 0.0), sensors=[radar, sat],
                             detection_delay=1.0, cue_delay=0.5)

    red = RedTEL("RED", position=(0.0, 0.0), speed=3000.0)
    red.launch_at_target((50.0, 0.0), launch_time=0.0, lofted=False)

    # Immediately after launch, the satellite already sees it (cue), but
    # the threat is far outside radar range (no track yet).
    c2.update([red], current_time=0.1)
    assert red.missile in c2.cues
    assert red.missile not in c2.tracks

    # Sweep forward in fixed steps — same polling pattern Simulation.run()
    # uses — until the threat closes into the radar's short ring.
    t = 0.1
    while t < red.missile.impact_time and red.missile not in c2.tracks:
        t += 0.5
        c2.update([red], current_time=t)

    assert red.missile in c2.tracks
    # the track's correlation delay is added on top of the moment of
    # radar acquisition, not the cue's
    assert c2.tracks[red.missile] >= t


def test_c2_without_fire_control_sensor_never_tracks():
    sat = SatelliteUnit("S", position=(0.0, 30.0))
    c2 = CommandControlUnit("C2", position=(0.0, 0.0), sensors=[sat], detection_delay=1.0)
    red = RedTEL("RED", position=(0.0, 0.0), speed=1500.0)
    red.launch_at_target((10.0, 0.0), launch_time=0.0, lofted=False)

    c2.update([red], current_time=0.1)
    assert red.missile in c2.cues
    assert red.missile not in c2.tracks


# ---------------------------------------------------------------------
# BlueTEL.compute_intercept: the returned velocity must actually deliver
# the interceptor to the predicted point in exactly `tof` seconds.
# ---------------------------------------------------------------------

def test_compute_intercept_solution_is_kinematically_consistent():
    red = RedTEL("RED", position=(0.0, 0.0), speed=1500.0)
    red.launch_at_target((30.0, 0.0), launch_time=0.0, lofted=False)

    blue = BlueTEL("BLUE", position=(30.0, 0.0), speed=3000.0, reaction_delay=1.0)
    solution = blue.compute_intercept(red.missile, detect_time=1.0)
    assert solution is not None
    launch_time, target_point, tof, (vx, vy) = solution

    origin_m = nm_to_m(blue.position)
    g = blue.gravity
    predicted_x = origin_m[0] + vx * tof
    predicted_y = origin_m[1] + vy * tof - 0.5 * g * tof ** 2
    np.testing.assert_allclose([predicted_x, predicted_y], target_point, atol=1.0)

    # and that target_point is really where the threat will be at that time
    np.testing.assert_allclose(red.missile.position(launch_time + tof), target_point, atol=1.0)


def test_compute_intercept_returns_none_when_target_too_fast_or_far():
    red = RedTEL("RED", position=(0.0, 0.0), speed=5000.0)
    red.launch_at_target((300.0, 0.0), launch_time=0.0, lofted=False)

    weak_blue = BlueTEL("BLUE", position=(300.0, 0.0), speed=1.0, reaction_delay=1.0)
    assert weak_blue.compute_intercept(red.missile, detect_time=1.0) is None
    assert weak_blue.intercept_solution is None


def test_launch_interceptor_without_solution_returns_none():
    blue = BlueTEL("BLUE", position=(0.0, 0.0), speed=1000.0)
    assert blue.launch_interceptor() is None
    assert blue.interceptor is None


def test_launch_interceptor_uses_solved_velocity():
    red = RedTEL("RED", position=(0.0, 0.0), speed=1500.0)
    red.launch_at_target((30.0, 0.0), launch_time=0.0, lofted=False)
    blue = BlueTEL("BLUE", position=(30.0, 0.0), speed=3000.0, reaction_delay=1.0)
    blue.compute_intercept(red.missile, detect_time=1.0)
    interceptor = blue.launch_interceptor()
    assert interceptor is blue.interceptor
    np.testing.assert_allclose(interceptor.velocity, blue.intercept_solution[3])
