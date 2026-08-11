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
battery), prints a per-threat report, opens an interactive 3D replay in
your browser, and appends the run to CSV logbooks under `output/logbook/`
— see [CSV logbook](#csv-logbook) below.

## Architecture

| Module | What it owns |
|---|---|
| [`msim/missile.py`](msim/missile.py) | `Missile` — the shared ballistic flight-body model (unpowered parabolic motion, closed-form impact time via the quadratic formula, not numerically integrated). Used identically by threats and interceptors. |
| [`msim/red_units.py`](msim/red_units.py) | `RedTEL` — solves the launch angle (or angle *and* speed, given a target apex height) that lands a shot exactly on a target, by algebraically inverting `Missile`'s own kinematics. |
| [`msim/blue_units.py`](msim/blue_units.py) | `RadarUnit`, `SatelliteUnit` (range-gated vs. always-on sensors, distinguished by a `fire_control_quality` flag), `CommandControlUnit` (two-tier sensor fusion: a coarse instant "cue" from any sensor vs. a correlation-delayed "track" that only a fire-control-quality sensor can produce), `BlueTEL` (predicted-intercept-point solver + interceptor launch), `HighValueAsset`. |
| [`msim/simulation.py`](msim/simulation.py) | `Simulation` — the tick loop tying it together: sensor fusion → greedy weapon-target assignment → position updates → intercept/leak resolution, for arbitrarily many threats and interceptors at once. |
| [`msim/units.py`](msim/units.py) | nm/knots ⇄ meters/m-per-s conversions. The public API (positions, speeds, ranges) is nautical miles and knots throughout; `Missile`'s internal physics stays SI since gravity is naturally expressed that way. |
| [`msim/export.py`](msim/export.py) + [`msim/viewer_template.html`](msim/viewer_template.html) | Converts a run to JSON and renders it into a self-contained, dependency-free 3D viewer (hand-rolled perspective projection on `<canvas>`, no Three.js) with a live per-threat status board. |
| [`msim/logbook.py`](msim/logbook.py) | Appends a completed run to the CSV logbooks — see below. |

The engagement resolution logic (who gets tracked, who gets assigned an
interceptor, what counts as a hit) is deliberately explicit rather than
hidden in a framework — see [`Simulation.run()`](msim/simulation.py) for
the actual per-tick sequencing. [`main.py`](main.py) is the only entry
point: it defines the demo scenario, runs it, and delivers the output
(viewer + logbook).

## CSV logbook

Every run of `python main.py` appends to three CSV files under
`output/logbook/` (created on first run; `output/` is gitignored, so
these are local-only history, not something you'd commit):

- **`runs.csv`** — one row per run: intercept/leaker tally, scenario
  parameters (`dt`, `t_max`, `intercept_radius_nm`, HVA position).
- **`threats.csv`** — one row per threat per run: outcome, speed, launch
  angle, launch/cue/detect/impact/intercept times, intercept point, which
  interceptor (if any) engaged it.
- **`sensors.csv`** — one row per sensor per run: type (radar/satellite),
  position, detection range (blank/unlimited for satellites, since
  they're not range-gated — see `SatelliteUnit` in
  [`msim/blue_units.py`](msim/blue_units.py)).

All three share a `run_timestamp` column (ISO-8601 UTC) so you can join
them — e.g. in a spreadsheet, or with pandas:

```python
import pandas as pd
runs = pd.read_csv("output/logbook/runs.csv")
threats = pd.read_csv("output/logbook/threats.csv")
threats.merge(runs, on="run_timestamp")
```

Run `main.py` a few times (it's deterministic — same scenario every time
— so the numbers will repeat, but this is exactly what you'd build on if
you started varying scenario parameters between runs) and open
`output/logbook/threats.csv` in Excel/Sheets to see it accumulate.

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov=msim
```

The suite (52 tests) focuses on *physical correctness*, not just "does it
run": e.g. `RedTEL.compute_launch_angle` is tested by actually propagating
the resulting `Missile` and asserting it lands on the target, not by
checking the angle against a hardcoded expected value. `tests/test_logbook.py`
covers the CSV logbook (using pytest's `tmp_path` fixture, so tests never
touch your real `output/logbook/`).

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

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs a syntax
check, the full test suite with coverage, and the performance benchmark
on every push/PR.
