# Missile Defense Simulation

A time-stepped engagement simulation: red ballistic threats vs. a blue
sensor/interceptor network defending a high-value asset. Everything
downstream — geometric radar-range detection, a two-tier sensor fusion
model (satellite cueing vs. radar-quality tracking), greedy weapon-target
assignment across multiple threats and multiple interceptors, and a
hand-rolled 3D visualization — sits on top of closed-form projectile
physics in [`msim/missile.py`](msim/missile.py).

Run it:

```bash
pip install -r requirements.txt
python main.py
```

That runs the demo scenario (a 3-missile raid against a 2-launcher
battery), prints a per-threat report, and opens an interactive 3D replay
in your browser.

## Architecture

| Module | What it owns |
|---|---|
| [`msim/missile.py`](msim/missile.py) | `Missile` — the shared ballistic flight-body model (unpowered parabolic motion, closed-form impact time via the quadratic formula, not numerically integrated). Used identically by threats and interceptors. |
| [`msim/red_units.py`](msim/red_units.py) | `RedTEL` — solves the launch angle (or angle *and* speed, given a target apex height) that lands a shot exactly on a target, by algebraically inverting `Missile`'s own kinematics. |
| [`msim/blue_units.py`](msim/blue_units.py) | `RadarUnit`, `SatelliteUnit` (range-gated vs. always-on sensors, distinguished by a `fire_control_quality` flag), `CommandControlUnit` (two-tier sensor fusion: a coarse instant "cue" from any sensor vs. a correlation-delayed "track" that only a fire-control-quality sensor can produce), `BlueTEL` (predicted-intercept-point solver + interceptor launch), `HighValueAsset`. |
| [`msim/simulation.py`](msim/simulation.py) | `Simulation` — the tick loop tying it together: sensor fusion → greedy weapon-target assignment → position updates → intercept/leak resolution, for arbitrarily many threats and interceptors at once. |
| [`msim/units.py`](msim/units.py) | nm/knots ⇄ meters/m-per-s conversions. The public API (positions, speeds, ranges) is nautical miles and knots throughout; `Missile`'s internal physics stays SI since gravity is naturally expressed that way. |
| [`msim/export.py`](msim/export.py) + [`msim/viewer_template.html`](msim/viewer_template.html) | Converts a run to JSON and renders it into a self-contained, dependency-free 3D viewer (hand-rolled perspective projection on `<canvas>`, no Three.js) with a live per-threat status board. |
| [`msim/db.py`](msim/db.py) | Optional PostgreSQL/CockroachDB persistence for run history — see [Database](#database) below. |

The engagement resolution logic (who gets tracked, who gets assigned an
interceptor, what counts as a hit) is deliberately explicit rather than
hidden in a framework — see [`Simulation.run()`](msim/simulation.py) for
the actual per-tick sequencing.

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov=msim
```

The suite (52 tests) focuses on *physical correctness*, not just "does it
run": e.g. `RedTEL.compute_launch_angle` is tested by actually propagating
the resulting `Missile` and asserting it lands on the target, not by
checking the angle against a hardcoded expected value. The database tests
(`tests/test_db.py`) need a live Postgres and skip cleanly without one —
point `DATABASE_URL` at one (e.g. `docker compose up postgres -d`) to run
them locally; CI always runs them against a real Postgres service
container.

## Performance

[`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) is a full writeup of a real
profiling pass: what I assumed the bottleneck was going in (the
interceptor solver's search loop), what `cProfile` actually showed
(redundant per-tick sensor-fusion work, not the solver), the fixes, and a
reproducible before/after benchmark showing a **1.5x** speedup at
constellation scale (40+ simulated threats/interceptors) — plus a note on
the bigger structural change (event-driven vs. fixed-timestep polling)
that would matter at another order of magnitude of scale.

```bash
python -m benchmarks.profile_engagement 40 25   # cProfile hotspot report
python -m benchmarks.bench_c2_update             # reproducible before/after
```

## Database

Optional. Persists completed runs (per-threat outcomes, timing, telemetry
summary — not the full per-tick trajectory history) to PostgreSQL or
CockroachDB for later querying/analysis, separate from the real-time
simulation itself. Schema: [`sql/schema.sql`](sql/schema.sql).

```bash
docker compose up postgres -d
export DATABASE_URL=postgresql://msim:msim@localhost:5432/msim
python main.py       # prints "Run persisted to database as runs.id=N"
```

`main.py`/`scripts/run_headless.py` only attempt persistence when
`DATABASE_URL` is set — the simulation and viewer work identically without
a database configured at all.

## Docker

```bash
docker compose up --build
```

Runs the full stack: Postgres (with a healthcheck gating startup order)
plus the app container, which runs the scenario headlessly (no browser in
a container), writes the 3D viewer HTML to `./output/` on the host via a
bind mount, and persists the run to the database. See
[`scripts/run_headless.py`](scripts/run_headless.py) for the
container-friendly entry point vs. [`main.py`](main.py)'s interactive one
— they share the same scenario definition
([`msim/scenario.py`](msim/scenario.py)) so there's exactly one place the
demo engagement is actually defined.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the test
suite (against a real Postgres service container, so the DB tests aren't
skipped in CI), a syntax check, the demo scenario end-to-end, the
performance benchmark, and a separate job that builds and runs the full
Docker Compose stack — so a broken container build fails CI the same way
a broken test would.
