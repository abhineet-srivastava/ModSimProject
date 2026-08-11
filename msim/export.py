"""Export a run Simulation's flight history to a JSON-serializable dict,
and render it into the standalone 3D HTML viewer.

Unit classes (RedTEL, BlueTEL, RadarUnit, SatelliteUnit,
CommandControlUnit, HighValueAsset) already store position in nautical
miles, so those pass through unchanged. Missile itself stays SI
internally, so anything read off a Missile object directly — sim.history
frames, a threat's intercept_point — is meters and needs converting."""

import json
import webbrowser
from pathlib import Path

from .blue_units import RadarUnit
from .units import m_to_nm

_TEMPLATE_PATH = Path(__file__).parent / "viewer_template.html"


def _pt(p):
    """Pass-through for positions already in nm (unit-class attributes)."""
    return None if p is None else [float(p[0]), float(p[1])]


def _pt_m(p):
    """Convert a Missile-native meters position to nm."""
    return None if p is None else [float(m_to_nm(p[0])), float(m_to_nm(p[1]))]


def export_engagement(sim):
    frames = [
        {
            "t": round(h["t"], 3),
            "reds": {name: _pt_m(pos) for name, pos in h["reds"].items()},
            "blues": {name: _pt_m(pos) for name, pos in h["blues"].items()},
        }
        for h in sim.history
    ]

    reds = []
    for red in sim.red_tels:
        status = sim.threat_status[red.name]
        reds.append({
            "name": red.name,
            "position": _pt(red.position),
            "target": _pt(red.target),
            "lateral_offset": float(red.lateral_offset),
            "speed": red.speed,
            "angle": red.launch_angle,
            "launch_time": red.missile.launch_time,
            "impact_time": red.missile.impact_time,
            "cue_time": sim.c2.cues.get(red.missile),
            "detect_time": sim.c2.tracks.get(red.missile),
            "outcome": status["outcome"],
            "intercept_time": status["intercept_time"],
            "intercept_point": _pt_m(status["intercept_point"]),
            "interceptor": status["interceptor"],
        })

    blues = [
        {
            "name": b.name,
            "position": _pt(b.position),
            "speed": b.speed,
            "launch_time": b.intercept_solution[0] if b.intercept_solution else None,
        }
        for b in sim.blue_tels
    ]

    radars, satellites = [], []
    for sensor in sim.c2.sensors:
        if isinstance(sensor, RadarUnit):
            radars.append({"name": sensor.name, "position": _pt(sensor.position),
                            "detection_range": sensor.detection_range})
        else:
            satellites.append({"name": sensor.name, "position": _pt(sensor.position)})

    hva = sim.hva

    return {
        "units": {"distance": "nm", "speed": "kn"},
        "dt": sim.dt,
        "hva_pos": _pt(hva.position) if hva is not None else None,
        "c2_pos": _pt(sim.c2.position),
        "reds": reds,
        "blues": blues,
        "radars": radars,
        "satellites": satellites,
        "frames": frames,
    }


def render_html_viewer(sim, output_path="output/engagement.html", open_browser=True):
    """Render the run Simulation into the standalone 3D HTML viewer and,
    by default, open it in the system's default browser."""
    data = export_engagement(sim)

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__ENGAGEMENT_DATA__", json.dumps(data))

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    if open_browser:
        webbrowser.open(out_path.resolve().as_uri())

    return out_path
