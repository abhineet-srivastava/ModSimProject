"""Persistence layer for completed engagement runs.

Targets the standard PostgreSQL wire protocol via psycopg2 — works
unmodified against PostgreSQL or CockroachDB. Opt-in: nothing in msim
requires a database, this is purely for persisting run history/telemetry
for later analysis (the "analysis pipelines that prove those systems are
working for our fleet" side of things, as opposed to the real-time
simulation itself).

Connection string comes from the DATABASE_URL environment variable, e.g.:
    postgresql://user:password@localhost:5432/msim
"""

import os
from pathlib import Path

import psycopg2
import psycopg2.extras

from .units import m_to_nm

_SCHEMA_PATH = Path(__file__).parent.parent / "sql" / "schema.sql"


def _f(x):
    """psycopg2 can't adapt numpy scalar types (np.float64 etc.), which
    several msim attributes are under the hood (anything that passed
    through a numpy computation) even though they look like plain floats.
    Coerce to a real Python float (or leave None alone) before binding."""
    return None if x is None else float(x)


def get_connection(database_url=None):
    """Open a connection using DATABASE_URL (or an explicit override).
    Raises if neither is set — callers decide whether that's fatal."""
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set and no database_url was given")
    return psycopg2.connect(url)


def init_schema(conn):
    """Apply sql/schema.sql. Idempotent (CREATE TABLE/INDEX IF NOT EXISTS)."""
    with conn.cursor() as cur:
        cur.execute(_SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def save_run(conn, sim):
    """Persist a completed Simulation run (must have already had .run()
    called on it) and return the new run's id."""
    intercepts = sum(1 for s in sim.threat_status.values() if s["outcome"] == "INTERCEPT")
    leakers = sum(1 for s in sim.threat_status.values() if s["outcome"] == "LEAKER")
    hva = sim.hva

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO runs (dt_seconds, t_max_seconds, intercept_radius_nm,
                               hva_name, hva_x_nm, hva_y_nm,
                               threat_count, interceptor_count, intercept_count, leaker_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                _f(sim.dt), _f(sim.t_max), _f(sim.intercept_radius),
                hva.name if hva else None,
                _f(hva.position[0]) if hva else None,
                _f(hva.position[1]) if hva else None,
                len(sim.red_tels), len(sim.blue_tels), intercepts, leakers,
            ),
        )
        run_id = cur.fetchone()[0]

        for red in sim.red_tels:
            status = sim.threat_status[red.name]
            intercept_point = status["intercept_point"]
            intercept_x_nm, intercept_y_nm = (None, None)
            if intercept_point is not None:
                intercept_x_nm = _f(m_to_nm(intercept_point[0]))
                intercept_y_nm = _f(m_to_nm(intercept_point[1]))

            cur.execute(
                """
                INSERT INTO threats (run_id, name, launch_x_nm, launch_y_nm, lateral_offset_nm,
                                      speed_kn, launch_angle_deg, launch_time_s, impact_time_s,
                                      cue_time_s, detect_time_s, outcome, intercept_time_s,
                                      intercept_x_nm, intercept_y_nm, interceptor_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id, red.name, _f(red.position[0]), _f(red.position[1]),
                    _f(red.lateral_offset), _f(red.speed), _f(red.launch_angle),
                    _f(red.missile.launch_time), _f(red.missile.impact_time),
                    _f(sim.c2.cues.get(red.missile)), _f(sim.c2.tracks.get(red.missile)),
                    status["outcome"], _f(status["intercept_time"]),
                    intercept_x_nm, intercept_y_nm, status["interceptor"],
                ),
            )

        for blue in sim.blue_tels:
            launch_time = blue.intercept_solution[0] if blue.intercept_solution else None
            cur.execute(
                """
                INSERT INTO interceptors (run_id, name, position_x_nm, position_y_nm, speed_kn, launch_time_s)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (run_id, blue.name, _f(blue.position[0]), _f(blue.position[1]), _f(blue.speed), _f(launch_time)),
            )

        for sensor in sim.c2.sensors:
            detection_range = getattr(sensor, "detection_range", None)  # None for satellites
            cur.execute(
                """
                INSERT INTO sensors (run_id, name, sensor_type, fire_control_quality,
                                      position_x_nm, position_y_nm, detection_range_nm)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id, sensor.name,
                    "radar" if sensor.fire_control_quality else "satellite",
                    sensor.fire_control_quality,
                    _f(sensor.position[0]), _f(sensor.position[1]), _f(detection_range),
                ),
            )

    conn.commit()
    return run_id


def fetch_recent_runs(conn, limit=10):
    """Summary rows for the most recent runs, newest first."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, created_at, threat_count, interceptor_count, intercept_count, leaker_count
            FROM runs
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def fetch_run_detail(conn, run_id):
    """A run's summary row plus all of its threats, interceptors, and sensors."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM runs WHERE id = %s", (run_id,))
        run = cur.fetchone()
        if run is None:
            return None

        cur.execute("SELECT * FROM threats WHERE run_id = %s ORDER BY id", (run_id,))
        threats = cur.fetchall()

        cur.execute("SELECT * FROM interceptors WHERE run_id = %s ORDER BY id", (run_id,))
        interceptors = cur.fetchall()

        cur.execute("SELECT * FROM sensors WHERE run_id = %s ORDER BY id", (run_id,))
        sensors = cur.fetchall()

    return {"run": run, "threats": threats, "interceptors": interceptors, "sensors": sensors}
