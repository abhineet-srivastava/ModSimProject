"""End-to-end Simulation.run(): sensor fusion, weapon-target assignment,
and outcome resolution together."""

import pytest

from msim import BlueTEL, HighValueAsset, RedTEL, Simulation


def test_easy_scenario_resolves_as_intercept(easy_intercept_sim):
    status = easy_intercept_sim.run(lofted=False)
    result = status["RED-TEST"]
    assert result["outcome"] == "INTERCEPT"
    assert result["interceptor"] == "BLUE-TEST"
    assert result["intercept_time"] is not None
    assert result["intercept_point"] is not None


def test_no_interceptors_available_always_leaks(guaranteed_leaker_sim):
    status = guaranteed_leaker_sim.run(lofted=False)
    result = status["RED-TEST"]
    assert result["outcome"] == "LEAKER"
    assert result["interceptor"] is None
    assert result["intercept_time"] is None


def test_intercepted_blue_stops_appearing_in_history_after_its_own_kill():
    """Regression test: an interceptor's underlying Missile keeps flying
    its programmed parabola past the moment it scored a hit (it has no
    idea it hit anything) — Simulation must stop surfacing its position in
    history once its assigned threat's outcome flips to INTERCEPT, or the
    3D viewer draws it sailing on through its own kill point.

    Needs a *second*, longer-flying, unengaged threat (only one BlueTEL is
    provided) so the simulation keeps running — and keeps recording
    frames — past the first threat's intercept instead of stopping the
    instant every threat has resolved."""
    from msim import CommandControlUnit, HighValueAsset, RadarUnit

    hva = HighValueAsset("HVA", position=(30.0, 0.0))
    radar = RadarUnit("R", position=(30.0, 0.0), detection_range=25.0)
    c2 = CommandControlUnit("C2", position=(30.0, 0.0), sensors=[radar], detection_delay=0.5)

    red_a = RedTEL("RED-A", position=(0.0, 0.0), speed=1500.0)   # gets intercepted quickly
    red_b = RedTEL("RED-B", position=(0.0, 0.0), max_altitude=15.0)  # lofted, long flight, never engaged
    blue = BlueTEL("BLUE", position=(30.0, 0.0), speed=3000.0, reaction_delay=1.0)

    sim = Simulation([red_a, red_b], [blue], c2, dt=0.1, t_max=300.0, intercept_radius=1.0, hva=hva)
    status = sim.run(red_launch_times=[0.0, 0.0], lofted=False)

    result = status["RED-A"]
    assert result["outcome"] == "INTERCEPT"
    t_hit = result["intercept_time"]

    frames_after_hit = [h for h in sim.history if h["t"] > t_hit + 0.5]
    assert frames_after_hit, "expected some frames after the intercept (RED-B should still be flying)"
    for h in frames_after_hit:
        assert "BLUE" not in h["blues"]
        assert "RED-A" not in h["reds"]


def test_more_threats_than_interceptors_leaves_some_unassigned():
    hva = HighValueAsset("HVA", position=(30.0, 0.0))
    reds = [
        RedTEL(f"RED-{i}", position=(0.0, 0.0), speed=1500.0)
        for i in range(3)
    ]
    blues = [BlueTEL("BLUE-0", position=(30.0, 0.0), speed=3000.0, reaction_delay=1.0)]

    from msim import CommandControlUnit, RadarUnit
    radar = RadarUnit("R", position=(30.0, 0.0), detection_range=25.0)
    c2 = CommandControlUnit("C2", position=(30.0, 0.0), sensors=[radar], detection_delay=0.5)

    sim = Simulation(reds, blues, c2, dt=0.1, t_max=200.0, intercept_radius=1.0, hva=hva)
    status = sim.run(red_launch_times=[0.0, 0.0, 0.0], lofted=False)

    assigned = [s for s in status.values() if s["interceptor"] is not None]
    unassigned = [s for s in status.values() if s["interceptor"] is None]
    assert len(assigned) == 1  # only one BlueTEL to go around
    assert len(unassigned) == 2
    for s in unassigned:
        assert s["outcome"] == "LEAKER"
    for s in status.values():
        assert s["outcome"] in ("INTERCEPT", "LEAKER")


def test_run_without_hva_or_explicit_targets_raises():
    red = RedTEL("RED", position=(0.0, 0.0), speed=1500.0)
    from msim import CommandControlUnit, RadarUnit
    radar = RadarUnit("R", position=(10.0, 0.0), detection_range=5.0)
    c2 = CommandControlUnit("C2", position=(10.0, 0.0), sensors=[radar])
    sim = Simulation([red], [], c2, hva=None)
    with pytest.raises(ValueError):
        sim.run()
