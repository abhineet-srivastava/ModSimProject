"""Missile is the shared ballistic flight-body model (unpowered parabolic
motion under constant gravity) used by both threats and interceptors.
These tests pin down its physics against closed-form projectile-motion
results, independent of any of the unit classes built on top of it."""

import numpy as np
import pytest

from msim.missile import Missile


def test_impact_time_matches_classic_time_of_flight_formula():
    # For a level launch (y0=0), time of flight is the textbook T = 2*vy/g.
    vy = 100.0
    g = 9.81
    m = Missile("M", launch_pos=(0, 0), velocity=(50, vy), launch_time=0.0, gravity=g)
    assert m.impact_time == pytest.approx(2 * vy / g)


def test_impact_time_offset_by_launch_time():
    m0 = Missile("M0", launch_pos=(0, 0), velocity=(50, 100), launch_time=0.0, gravity=9.81)
    m5 = Missile("M5", launch_pos=(0, 0), velocity=(50, 100), launch_time=5.0, gravity=9.81)
    assert m5.impact_time == pytest.approx(m0.impact_time + 5.0)


def test_position_at_launch_equals_launch_pos():
    m = Missile("M", launch_pos=(10, 20), velocity=(50, 100), launch_time=3.0, gravity=9.81)
    np.testing.assert_allclose(m.position(3.0), [10, 20])


def test_position_before_launch_is_none():
    m = Missile("M", launch_pos=(0, 0), velocity=(50, 100), launch_time=3.0, gravity=9.81)
    assert m.position(2.999) is None


def test_apex_height_matches_vy_squared_over_2g():
    vy = 100.0
    g = 9.81
    m = Missile("M", launch_pos=(0, 0), velocity=(50, vy), launch_time=0.0, gravity=g)
    t_apex = vy / g
    apex_y = m.position(t_apex)[1]
    assert apex_y == pytest.approx(vy ** 2 / (2 * g))


def test_horizontal_motion_is_constant_velocity():
    vx = 50.0
    m = Missile("M", launch_pos=(0, 0), velocity=(vx, 100), launch_time=0.0, gravity=9.81)
    assert m.position(4.0)[0] == pytest.approx(vx * 4.0)


def test_position_clamps_to_ground_past_impact_time():
    m = Missile("M", launch_pos=(0, 0), velocity=(50, 100), launch_time=0.0, gravity=9.81)
    far_future = m.position(m.impact_time + 1000.0)
    at_impact = m.position(m.impact_time)
    np.testing.assert_allclose(far_future, at_impact)
    assert far_future[1] == pytest.approx(0.0, abs=1e-6)


def test_is_active_bounds():
    m = Missile("M", launch_pos=(0, 0), velocity=(50, 100), launch_time=2.0, gravity=9.81)
    assert not m.is_active(1.999)
    assert m.is_active(2.0)
    assert m.is_active(m.impact_time)
    assert not m.is_active(m.impact_time + 0.001)


def test_impact_time_falls_back_to_launch_time_when_unreachable():
    # Launched from deep underground with too little upward speed to ever
    # reach y=0: the quadratic's discriminant goes negative, and
    # _compute_impact_time defensively falls back to launch_time rather
    # than raising or returning NaN.
    m = Missile("M", launch_pos=(0, -1000), velocity=(0, 1), launch_time=7.0, gravity=9.81)
    assert m.impact_time == 7.0
