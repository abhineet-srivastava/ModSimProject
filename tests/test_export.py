"""export_engagement() must hand the viewer everything in nm/knots, having
converted anything that came straight off a Missile object (which stays
SI/meters internally)."""

import pytest

from msim.export import export_engagement
from msim.units import m_to_nm


def test_export_unit_positions_pass_through_unchanged(easy_intercept_sim):
    easy_intercept_sim.run(lofted=False)
    data = export_engagement(easy_intercept_sim)

    assert data["units"] == {"distance": "nm", "speed": "kn"}
    assert data["hva_pos"] == [20.0, 0.0]
    red = next(r for r in data["reds"] if r["name"] == "RED-TEST")
    assert red["position"] == [0.0, 0.0]


def test_export_frame_positions_are_converted_from_meters_to_nm(easy_intercept_sim):
    sim = easy_intercept_sim
    sim.run(lofted=False)
    data = export_engagement(sim)

    # cross-check one frame directly against the raw (meters) history
    raw = next(h for h in sim.history if "RED-TEST" in h["reds"])
    exported = next(f for f in data["frames"] if "RED-TEST" in f["reds"])
    raw_pos_m = raw["reds"]["RED-TEST"]
    exported_pos_nm = exported["reds"]["RED-TEST"]
    assert exported_pos_nm[0] == pytest.approx(m_to_nm(raw_pos_m[0]), abs=1e-6)
    assert exported_pos_nm[1] == pytest.approx(m_to_nm(raw_pos_m[1]), abs=1e-6)


def test_export_includes_intercept_outcome_fields(easy_intercept_sim):
    easy_intercept_sim.run(lofted=False)
    data = export_engagement(easy_intercept_sim)
    red = next(r for r in data["reds"] if r["name"] == "RED-TEST")
    assert red["outcome"] == "INTERCEPT"
    assert red["interceptor"] == "BLUE-TEST"
    assert red["intercept_point"] is not None
    assert red["intercept_time"] is not None


def test_export_sensor_lists_split_by_fire_control_quality(easy_intercept_sim):
    easy_intercept_sim.run(lofted=False)
    data = export_engagement(easy_intercept_sim)
    assert len(data["radars"]) == 1
    assert data["radars"][0]["name"] == "RADAR-TEST"
    assert data["satellites"] == []
