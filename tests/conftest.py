"""Shared pytest fixtures: small, fast, deterministic scenarios.

Ranges are kept short (single-digit to low-double-digit nm) so the
Simulation.run() loop used by integration tests resolves in well under a
second of wall-clock test time, regardless of dt.
"""

import pytest

from msim import (
    BlueTEL,
    CommandControlUnit,
    HighValueAsset,
    RadarUnit,
    RedTEL,
    SatelliteUnit,
    Simulation,
)


@pytest.fixture
def hva():
    return HighValueAsset("HVA-TEST", position=(20.0, 0.0))


@pytest.fixture
def radar():
    return RadarUnit("RADAR-TEST", position=(20.0, 0.0), detection_range=15.0)


@pytest.fixture
def satellite():
    return SatelliteUnit("SAT-TEST", position=(10.0, 20.0))


@pytest.fixture
def c2(radar):
    return CommandControlUnit("C2-TEST", position=(20.0, 0.0), sensors=[radar], detection_delay=0.5)


@pytest.fixture
def c2_with_satellite(radar, satellite):
    return CommandControlUnit(
        "C2-TEST", position=(20.0, 0.0), sensors=[radar, satellite], detection_delay=0.5, cue_delay=0.2
    )


@pytest.fixture
def easy_intercept_sim(hva, c2):
    """A single threat, single interceptor, generously easy geometry —
    should reliably resolve as INTERCEPT. lofted=False (flat, fast shot)
    keeps flight time short and, combined with a 1nm intercept radius,
    comfortably absorbs the position error introduced by dt=0.1 tick
    quantization (the exact geometric meeting instant is a real number that
    generally doesn't land exactly on a sampled tick) — see
    docs/PERFORMANCE.md and the dt-vs-intercept_radius discussion there."""
    red = RedTEL("RED-TEST", position=(0.0, 0.0), speed=1500.0)
    blue = BlueTEL("BLUE-TEST", position=(20.0, 0.0), speed=3000.0, reaction_delay=1.0)
    sim = Simulation([red], [blue], c2, dt=0.1, t_max=200.0, intercept_radius=1.0, hva=hva)
    return sim


@pytest.fixture
def guaranteed_leaker_sim(hva, c2):
    """A single threat with no interceptors at all — must leak."""
    red = RedTEL("RED-TEST", position=(0.0, 0.0), speed=1500.0)
    sim = Simulation([red], [], c2, dt=0.1, t_max=200.0, intercept_radius=1.0, hva=hva)
    return sim
