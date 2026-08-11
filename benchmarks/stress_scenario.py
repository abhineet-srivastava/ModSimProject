"""Builds a constellation-scale stress scenario (many more threats and
interceptors than the small hand-tuned demo in main.py) for profiling and
benchmarking — the default demo is too small to show a hot path clearly."""

from msim import (
    BlueTEL,
    CommandControlUnit,
    HighValueAsset,
    RadarUnit,
    RedTEL,
    SatelliteUnit,
    Simulation,
)


def build_stress_scenario(n_reds=40, n_blues=25, seed_spacing=3.0):
    hva = HighValueAsset("HVA-1", position=(300.0, 0.0))

    red_tels = []
    for i in range(n_reds):
        rng = 80.0 + (i % 7) * 20.0  # 80..200nm, repeating pattern for variety
        loft = 0.18 + (i % 5) * 0.03  # 0.18..0.30
        red_tels.append(RedTEL(
            f"RED-{i}",
            position=(hva.position[0] - rng, 0.0),
            max_altitude=rng * loft,
            lateral_offset=(i - n_reds / 2) * seed_spacing,
        ))
    red_launch_times = [0.0] * n_reds

    blue_tels = [
        BlueTEL(f"BLUE-{i}", position=(hva.position[0] - 2.0 + i * 0.1, 0.0),
                speed=3400.0, reaction_delay=3.0)
        for i in range(n_blues)
    ]
    radar = RadarUnit("RADAR-1", position=(hva.position[0] - 2.0, 0.0), detection_range=60.0)
    satellite = SatelliteUnit("SAT-1", position=(hva.position[0] - 100.0, 60.0))
    c2 = CommandControlUnit("C2-ALPHA", position=(hva.position[0] - 1.5, 0.0),
                             sensors=[radar, satellite], detection_delay=1.5)

    sim = Simulation(red_tels, blue_tels, c2, dt=0.05, t_max=600.0, intercept_radius=0.02, hva=hva)
    return sim, red_launch_times
