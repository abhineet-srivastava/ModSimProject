"""Unit conversion round-trips and known reference values."""

import pytest

from msim.units import knots_to_mps, m_to_nm, mps_to_knots, nm_to_m


def test_nm_to_m_known_value():
    # 1 nautical mile is defined as exactly 1852 meters.
    assert nm_to_m(1.0) == 1852.0


def test_knot_is_one_nm_per_hour():
    # 1 knot = 1 nm / 3600s, so traveling at 1 knot for 3600s covers 1852m.
    assert knots_to_mps(1.0) * 3600 == pytest.approx(1852.0)


@pytest.mark.parametrize("nm", [0.0, 1.0, 42.5, 1234.567, -3.0])
def test_nm_m_round_trip(nm):
    assert m_to_nm(nm_to_m(nm)) == pytest.approx(nm)


@pytest.mark.parametrize("knots", [0.0, 1.0, 500.0, 3889.0])
def test_knots_mps_round_trip(knots):
    assert mps_to_knots(knots_to_mps(knots)) == pytest.approx(knots)
