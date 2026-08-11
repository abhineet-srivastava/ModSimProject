"""Appends each completed run to a set of CSV logbooks — a flat-file
alternative to a database: no server to run, just files that accumulate
history across every run of the simulation.

Three files, joined by run_timestamp (an ISO-8601 UTC string, unique per
run since nothing else needs to generate a run id anymore):

- runs.csv     one row per run: intercept/leaker tally, scenario params
- threats.csv  one row per threat per run: outcome, speed, angle, timing
- sensors.csv  one row per sensor per run: type, position, detection range
"""

import csv
from datetime import datetime, timezone
from pathlib import Path

from .units import m_to_nm

_RUN_FIELDS = [
    "run_timestamp", "threat_count", "interceptor_count", "intercept_count", "leaker_count",
    "dt_seconds", "t_max_seconds", "intercept_radius_nm",
    "hva_name", "hva_x_nm", "hva_y_nm",
]

_THREAT_FIELDS = [
    "run_timestamp", "name", "outcome", "speed_kn", "launch_angle_deg",
    "launch_x_nm", "launch_y_nm", "lateral_offset_nm",
    "launch_time_s", "cue_time_s", "detect_time_s", "impact_time_s",
    "intercept_time_s", "intercept_x_nm", "intercept_y_nm", "interceptor_name",
]

_SENSOR_FIELDS = [
    "run_timestamp", "name", "sensor_type", "fire_control_quality",
    "position_x_nm", "position_y_nm", "detection_range_nm",
]


def _append_rows(path, fieldnames, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def append_run(sim, logbook_dir="output/logbook"):
    """Append a completed Simulation run to the CSV logbooks and return
    the run_timestamp used to join its rows across the three files."""
    logbook_dir = Path(logbook_dir)
    run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    intercepts = sum(1 for s in sim.threat_status.values() if s["outcome"] == "INTERCEPT")
    leakers = sum(1 for s in sim.threat_status.values() if s["outcome"] == "LEAKER")
    hva = sim.hva

    _append_rows(logbook_dir / "runs.csv", _RUN_FIELDS, [{
        "run_timestamp": run_timestamp,
        "threat_count": len(sim.red_tels),
        "interceptor_count": len(sim.blue_tels),
        "intercept_count": intercepts,
        "leaker_count": leakers,
        "dt_seconds": sim.dt,
        "t_max_seconds": sim.t_max,
        "intercept_radius_nm": sim.intercept_radius,
        "hva_name": hva.name if hva else None,
        "hva_x_nm": float(hva.position[0]) if hva else None,
        "hva_y_nm": float(hva.position[1]) if hva else None,
    }])

    threat_rows = []
    for red in sim.red_tels:
        status = sim.threat_status[red.name]
        intercept_point = status["intercept_point"]
        intercept_x_nm = intercept_y_nm = None
        if intercept_point is not None:
            intercept_x_nm = float(m_to_nm(intercept_point[0]))
            intercept_y_nm = float(m_to_nm(intercept_point[1]))

        threat_rows.append({
            "run_timestamp": run_timestamp,
            "name": red.name,
            "outcome": status["outcome"],
            "speed_kn": red.speed,
            "launch_angle_deg": red.launch_angle,
            "launch_x_nm": float(red.position[0]),
            "launch_y_nm": float(red.position[1]),
            "lateral_offset_nm": float(red.lateral_offset),
            "launch_time_s": red.missile.launch_time,
            "cue_time_s": sim.c2.cues.get(red.missile),
            "detect_time_s": sim.c2.tracks.get(red.missile),
            "impact_time_s": red.missile.impact_time,
            "intercept_time_s": status["intercept_time"],
            "intercept_x_nm": intercept_x_nm,
            "intercept_y_nm": intercept_y_nm,
            "interceptor_name": status["interceptor"],
        })
    _append_rows(logbook_dir / "threats.csv", _THREAT_FIELDS, threat_rows)

    sensor_rows = []
    for sensor in sim.c2.sensors:
        detection_range = getattr(sensor, "detection_range", None)  # None for satellites
        sensor_rows.append({
            "run_timestamp": run_timestamp,
            "name": sensor.name,
            "sensor_type": "radar" if sensor.fire_control_quality else "satellite",
            "fire_control_quality": sensor.fire_control_quality,
            "position_x_nm": float(sensor.position[0]),
            "position_y_nm": float(sensor.position[1]),
            "detection_range_nm": detection_range,
        })
    _append_rows(logbook_dir / "sensors.csv", _SENSOR_FIELDS, sensor_rows)

    return run_timestamp
