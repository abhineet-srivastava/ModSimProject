"""RedTEL's targeting solvers: verify the angle (or angle+speed) they
compute actually delivers the resulting Missile onto the target, not just
that they return *a* number. This is the property that matters — the
formulas are inverses of Missile's own kinematics, so if they're wrong the
missile simply won't arrive where it's supposed to."""

import numpy as np
import pytest

from msim.red_units import RedTEL
from msim.units import nm_to_m


def _lands_on(missile, target_pos_nm, tol_m=1.0):
    """True if the missile's trajectory passes through target_pos_nm at
    some point (checked at its own impact instant, since compute_launch_angle
    solves for exactly the impact point)."""
    target_m = nm_to_m(np.asarray(target_pos_nm, dtype=float))
    actual_m = missile.position(missile.impact_time)
    return np.allclose(actual_m, target_m, atol=tol_m)


@pytest.mark.parametrize("lofted", [True, False])
def test_compute_launch_angle_hits_target(lofted):
    red = RedTEL("RED", position=(0.0, 0.0), speed=1500.0)
    target = (10.0, 0.0)  # nm, level ground
    red.launch_at_target(target, launch_time=0.0, lofted=lofted)
    assert _lands_on(red.missile, target)


def test_lofted_and_flat_solutions_differ():
    red_lofted = RedTEL("RED-L", position=(0.0, 0.0), speed=1500.0)
    red_flat = RedTEL("RED-F", position=(0.0, 0.0), speed=1500.0)
    target = (10.0, 0.0)
    red_lofted.launch_at_target(target, launch_time=0.0, lofted=True)
    red_flat.launch_at_target(target, launch_time=0.0, lofted=False)
    assert red_lofted.launch_angle > red_flat.launch_angle
    # both still land on the same target
    assert _lands_on(red_lofted.missile, target)
    assert _lands_on(red_flat.missile, target)


def test_compute_launch_angle_raises_when_target_out_of_range():
    red = RedTEL("RED", position=(0.0, 0.0), speed=1.0)  # far too slow
    with pytest.raises(ValueError):
        red.compute_launch_angle((500.0, 0.0), speed_knots=1.0)


def test_compute_apex_solution_hits_target_and_requested_apex():
    red = RedTEL("RED", position=(0.0, 0.0), max_altitude=8.0)
    target = (30.0, 0.0)  # nm
    red.launch_at_target(target, launch_time=0.0)

    assert _lands_on(red.missile, target)

    # sample the trajectory densely and confirm the true max altitude
    # matches the requested apex (within sampling resolution)
    ts = np.linspace(0, red.missile.impact_time, 5000)
    ys_nm = [red.missile.position(t)[1] / 1852.0 for t in ts]
    assert max(ys_nm) == pytest.approx(8.0, abs=0.01)


def test_max_altitude_overrides_configured_speed():
    red = RedTEL("RED", position=(0.0, 0.0), speed=9999.0, max_altitude=5.0)
    red.launch_at_target((20.0, 0.0), launch_time=0.0)
    # speed is a *derived* result when max_altitude is set — the
    # configured 9999 kn placeholder must not survive the launch.
    assert red.speed != 9999.0


def test_apex_below_launch_altitude_raises():
    red = RedTEL("RED", position=(0.0, 0.0), max_altitude=-1.0)
    with pytest.raises(ValueError):
        red.launch_at_target((20.0, 0.0), launch_time=0.0)


def test_launch_without_speed_or_max_altitude_raises():
    red = RedTEL("RED", position=(0.0, 0.0))
    with pytest.raises(ValueError):
        red.launch_at_target((20.0, 0.0), launch_time=0.0)


def test_launch_at_target_records_target_and_angle():
    red = RedTEL("RED", position=(0.0, 0.0), speed=1500.0)
    red.launch_at_target((10.0, 0.0), launch_time=0.0, lofted=False)
    np.testing.assert_allclose(red.target, [10.0, 0.0])
    assert red.launch_angle is not None
    assert red.missile is not None
