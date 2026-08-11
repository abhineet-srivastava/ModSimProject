"""Container/CI-friendly entry point: same scenario as main.py, but never
opens a browser (there isn't one in a container) and persists to the
database whenever DATABASE_URL is set — which it always is in
docker-compose's `app` service. Run directly with `python -m
scripts.run_headless` for the same behavior outside a container too.
"""

import os
import sys
from pathlib import Path

# Allow running this file directly, not just as `python -m scripts.run_headless`
# — see the matching comment in scripts/report.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from msim.export import render_html_viewer
from msim.scenario import build_and_run, print_report


def main():
    sim = build_and_run()
    print_report(sim)

    output_dir = os.environ.get("OUTPUT_DIR", "output")
    out_path = render_html_viewer(sim, output_path=os.path.join(output_dir, "engagement.html"), open_browser=False)
    print(f"3D viewer written to {out_path}")

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        from msim import db
        conn = db.get_connection(database_url)
        try:
            db.init_schema(conn)
            run_id = db.save_run(conn, sim)
            print(f"Run persisted to database as runs.id={run_id}")
        finally:
            conn.close()
    else:
        print("DATABASE_URL not set — skipping persistence", file=sys.stderr)


if __name__ == "__main__":
    main()
