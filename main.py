"""Interactive entry point: run the demo engagement, open the 3D viewer in
a browser, and persist to the database if DATABASE_URL is set. See
msim/scenario.py for the scenario itself and scripts/run_headless.py for
the container/CI-friendly (no browser, always-persist) variant."""

import os

from msim.export import render_html_viewer
from msim.scenario import build_and_run, print_report


def main():
    sim = build_and_run()
    print_report(sim)

    out_path = render_html_viewer(sim)
    print(f"3D viewer written to {out_path} (opening in browser)")

    if os.environ.get("DATABASE_URL"):
        from msim import db
        conn = db.get_connection()
        try:
            db.init_schema(conn)
            run_id = db.save_run(conn, sim)
            print(f"Run persisted to database as runs.id={run_id}")
        finally:
            conn.close()


if __name__ == "__main__":
    main()
