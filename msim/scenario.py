"""The demo scenario, factored out of main.py so both the interactive
entrypoint (main.py, opens a browser) and the headless one
(scripts/run_headless.py, for containers/CI) build and run the exact same
engagement without duplicating it.

All positions/ranges are nautical miles (nm), all speeds are knots (kn).

Scenario: a simultaneous 3-missile raid, launched horizontally aligned —
same range from the HVA, spread side-by-side — against a defended
high-value asset, covered by one ground radar, one early-warning
satellite, and a 2-launcher interceptor battery — fewer interceptors than
inbound threats, so not everything is guaranteed to be stopped. The
satellite gives early cueing the instant any missile is airborne, but
weapons release still requires the radar's fire-control-quality track
(CommandControlUnit.tracks, gated on sensor.fire_control_quality) — so
interceptors don't launch until a threat is actually inside the radar's
dome, even though C2 knew about it earlier."""

from msim import (
    BlueTEL,
    CommandControlUnit,
    HighValueAsset,
    RadarUnit,
    RedTEL,
    SatelliteUnit,
    Simulation,
)
from msim.units import m_to_nm


def build_and_run():
    """Construct the demo scenario, run it to resolution, and return the
    Simulation (already run) for callers to export/persist/report on."""
    hva = HighValueAsset("HVA-1", position=(150, 0))

    # Red raid: all three TELs at the same range from the HVA — a
    # horizontal firing line — but dispersed at least 70nm apart laterally
    # (real launch sites, not stacked on the same spot; a dispersed battery
    # avoids a single counterstrike taking out every launcher). Each still
    # aims at the same HVA (Simulation.run() defaults red_targets to
    # hva.position for every TEL) and has its own loft ratio so their
    # speed/altitude profiles stay distinguishable. All three launch
    # simultaneously.
    RED_RANGE = 100
    red_x = hva.position[0] - RED_RANGE
    red_tels = [
        RedTEL("RED-1", position=(red_x, 0), max_altitude=RED_RANGE * 0.22, lateral_offset=-70.0),
        RedTEL("RED-2", position=(red_x, 0), max_altitude=RED_RANGE * 0.28, lateral_offset=0.0),
        RedTEL("RED-3", position=(red_x, 0), max_altitude=RED_RANGE * 0.33, lateral_offset=70.0),
    ]
    red_launch_times = [0.0, 0.0, 0.0]

    # Blue interceptor battery: two launchers, a shared radar/C2, and one
    # early-warning satellite for wide-area cueing ahead of radar range.
    blue_tels = [
        BlueTEL("BLUE-1", position=(148.0, 0), speed=3400.0, reaction_delay=3.0),
        BlueTEL("BLUE-2", position=(148.4, 0), speed=3400.0, reaction_delay=3.0),
    ]
    radar = RadarUnit("RADAR-1", position=(148.0, 0), detection_range=40.0)
    satellite = SatelliteUnit("SAT-1", position=(90, 45))
    c2 = CommandControlUnit("C2-ALPHA", position=(148.5, 0), sensors=[radar, satellite], detection_delay=1.5)

    sim = Simulation(red_tels, blue_tels, c2, dt=0.05, t_max=500.0, intercept_radius=0.02, hva=hva)
    sim.run(red_launch_times=red_launch_times, lofted=False)
    return sim


def print_report(sim):
    intercepts = sum(1 for s in sim.threat_status.values() if s["outcome"] == "INTERCEPT")
    leakers = sum(1 for s in sim.threat_status.values() if s["outcome"] == "LEAKER")
    print(f"Engagement complete: {intercepts} INTERCEPT / {leakers} LEAKER (of {len(sim.red_tels)} threats)")
    for red in sim.red_tels:
        status = sim.threat_status[red.name]
        line = f"  {red.name}: {status['outcome']}, angle={red.launch_angle:.1f} deg, speed={red.speed:.0f} kn"
        if status["interceptor"]:
            line += f", engaged by {status['interceptor']}"
        if status["intercept_time"] is not None:
            p = m_to_nm(status["intercept_point"])
            line += f", at t={status['intercept_time']:.1f}s point=({p[0]:.2f}, {p[1]:.2f}) nm"
        print(line)
