"""Query persisted runs from the database and print a readable report:
overall intercept/leaker tallies, per-threat detail, and sensor detection
ranges — the "analysis pipeline" side of things, reading back what
main.py / scripts/run_headless.py wrote.

Usage:
    python -m scripts.report                  # summary of recent runs
    python -m scripts.report --run-id 5        # full detail for run 5
    python -m scripts.report --latest           # full detail for the most recent run
    python -m scripts.report --limit 20         # more rows in the summary view
"""

import argparse
import sys
from pathlib import Path

# Allow running this file directly (e.g. an IDE's "Run" button invokes
# `python scripts/report.py`, which only puts scripts/ on sys.path, not
# the project root) as well as the recommended `python -m scripts.report`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2

from msim import db


def _line(char="-", width=78):
    print(char * width)


def print_summary(conn, limit):
    runs = db.fetch_recent_runs(conn, limit=limit)
    if not runs:
        print("No runs recorded yet. Run `python main.py` (with DATABASE_URL set) first.")
        return

    _line("=")
    print(f"RECENT RUNS ({len(runs)})")
    _line("=")
    print(f"{'ID':>4}  {'CREATED (UTC)':<20}  {'THREATS':>7}  {'INTERCEPTORS':>12}  {'INTERCEPT':>9}  {'LEAK':>4}")
    _line()
    for run in runs:
        print(
            f"{run['id']:>4}  {run['created_at'].strftime('%Y-%m-%d %H:%M:%S'):<20}  "
            f"{run['threat_count']:>7}  {run['interceptor_count']:>12}  "
            f"{run['intercept_count']:>9}  {run['leaker_count']:>4}"
        )
    _line()
    print(f"\nFor full detail on one run: python -m scripts.report --run-id {runs[0]['id']}")


def print_detail(conn, run_id):
    detail = db.fetch_run_detail(conn, run_id)
    if detail is None:
        print(f"No run with id={run_id}")
        return

    run = detail["run"]
    threats = detail["threats"]
    interceptors = detail["interceptors"]
    sensors = detail["sensors"]

    _line("=")
    print(f"RUN {run['id']}  -  {run['created_at'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
    _line("=")
    print(f"HVA: {run['hva_name']} @ ({run['hva_x_nm']:.1f}, {run['hva_y_nm']:.1f}) nm")
    print(f"dt={run['dt_seconds']}s   t_max={run['t_max_seconds']}s   intercept_radius={run['intercept_radius_nm']}nm")
    print()
    total = run["threat_count"]
    pct = (run["intercept_count"] / total * 100) if total else 0.0
    print(f"OUTCOME: {run['intercept_count']}/{total} INTERCEPTED ({pct:.0f}%)   "
          f"{run['leaker_count']}/{total} LEAKED   {run['interceptor_count']} interceptor(s) available")

    print()
    _line()
    print("SENSORS")
    _line()
    print(f"{'NAME':<12} {'TYPE':<10} {'FIRE CTRL':<9} {'POSITION (nm)':<18} {'DETECTION RANGE':>16}")
    for s in sensors:
        pos = f"({s['position_x_nm']:.1f}, {s['position_y_nm']:.1f})"
        rng = f"{s['detection_range_nm']:.1f} nm" if s["detection_range_nm"] is not None else "unlimited"
        print(f"{s['name']:<12} {s['sensor_type']:<10} {str(s['fire_control_quality']):<9} {pos:<18} {rng:>16}")

    print()
    _line()
    print("THREATS")
    _line()
    print(f"{'NAME':<8} {'OUTCOME':<10} {'SPEED (kn)':>10} {'ANGLE':>7} {'DETECT (s)':>10} {'IMPACT (s)':>10} {'ENGAGED BY':<12}")
    for t in threats:
        speed = f"{t['speed_kn']:.0f}" if t["speed_kn"] is not None else "-"
        angle = f"{t['launch_angle_deg']:.1f}" if t["launch_angle_deg"] is not None else "-"
        detect = f"{t['detect_time_s']:.1f}" if t["detect_time_s"] is not None else "-"
        impact = f"{t['impact_time_s']:.1f}" if t["impact_time_s"] is not None else "-"
        engaged = t["interceptor_name"] or "-"
        print(f"{t['name']:<8} {t['outcome']:<10} {speed:>10} {angle:>7} {detect:>10} {impact:>10} {engaged:<12}")

    print()
    _line()
    print("INTERCEPTORS")
    _line()
    print(f"{'NAME':<10} {'SPEED (kn)':>10} {'POSITION (nm)':<18} {'LAUNCH TIME (s)':>16}")
    for b in interceptors:
        pos = f"({b['position_x_nm']:.1f}, {b['position_y_nm']:.1f})"
        launch = f"{b['launch_time_s']:.1f}" if b["launch_time_s"] is not None else "never launched"
        print(f"{b['name']:<10} {b['speed_kn']:>10.0f} {pos:<18} {launch:>16}")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", type=int, help="Show full detail for this run id")
    parser.add_argument("--latest", action="store_true", help="Show full detail for the most recent run")
    parser.add_argument("--limit", type=int, default=10, help="How many runs to list in summary view (default 10)")
    args = parser.parse_args()

    try:
        conn = db.get_connection()
    except RuntimeError:
        print("DATABASE_URL is not set.", file=sys.stderr)
        print("Set it to point at a running Postgres, e.g.:", file=sys.stderr)
        print('  PowerShell:  $env:DATABASE_URL = "postgresql://msim:msim@localhost:5432/msim"', file=sys.stderr)
        print('  bash:        export DATABASE_URL="postgresql://msim:msim@localhost:5432/msim"', file=sys.stderr)
        print("(start one with: docker compose up postgres -d)", file=sys.stderr)
        sys.exit(1)
    except psycopg2.OperationalError as e:
        print(f"Could not connect to the database: {e}", file=sys.stderr)
        print("Is Postgres running? Start it with: docker compose up postgres -d", file=sys.stderr)
        sys.exit(1)

    try:
        db.init_schema(conn)
        if args.latest:
            recent = db.fetch_recent_runs(conn, limit=1)
            if not recent:
                print("No runs recorded yet.")
                return
            print_detail(conn, recent[0]["id"])
        elif args.run_id is not None:
            print_detail(conn, args.run_id)
        else:
            print_summary(conn, args.limit)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
