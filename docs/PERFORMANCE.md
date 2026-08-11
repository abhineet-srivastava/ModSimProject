# Performance investigation

## Methodology

The default demo scenario in `main.py` (3 threats, 2 interceptors) runs in
well under a second and isn't representative of anything worth profiling.
[`benchmarks/stress_scenario.py`](../benchmarks/stress_scenario.py) builds
a constellation-scale scenario instead — 40 threats and 25 interceptors by
default, configurable — closer to what an actual fleet-tracking workload
looks like.

[`benchmarks/profile_engagement.py`](../benchmarks/profile_engagement.py)
runs that scenario under `cProfile` and prints the hottest functions by
cumulative time:

```
python -m benchmarks.profile_engagement 40 25
```

## What I assumed vs. what profiling actually showed

Going in, the obvious suspect looked like `BlueTEL.compute_intercept()` —
it does a linear search over candidate times-of-flight in fixed
`tof_step` increments, which *looks* like the kind of O(n) loop worth
vectorizing. Profiling said otherwise: at 40v25 scale it accounted for
**0.07s of a 1.98s run (~3.5%)** — it only runs once per threat, when a
weapon gets assigned, not every tick. Optimizing it first would have been
effort spent on a function that wasn't the bottleneck.

The actual hotspot was `CommandControlUnit.update()` — **1.13s, 57% of
total runtime** — called once per simulation tick (thousands of times)
and, for every tick, for every still-airborne threat, it:

1. Recomputed `missile.position(t)` even for threats that had already
   been fully cued *and* tracked — there was nothing left to determine
   about them, but the sensor-range checks ran anyway for the rest of
   their flight.
2. Ran through `RadarUnit.in_range()`, which reconverted its own
   `position` and `detection_range` from nautical miles to meters —
   values that never change after construction — on *every single call*
   (`nm_to_m()` showed up 228,615 times in the profile).
3. Rebuilt the `fire_control_quality` sensor sublist from scratch on
   every call, another loop-invariant recomputed every tick.
4. Duplicated work already done a few lines away: `Simulation.run()`
   calls `red.missile.position(t)` again immediately afterward to build
   its own history/intercept-check data for the same red at the same
   instant.

None of these are algorithmic-complexity problems — they're all "doing
the same fixed-cost work more times than necessary." That's a more
common category of real-world bottleneck than a bad Big-O choice, and
worth checking for before reaching for something more invasive.

## Fixes

- **`RadarUnit`**: convert `position`/`detection_range` to meters once at
  construction (`self._position_m`, `self._range_m`), not on every
  `in_range()` call.
- **`CommandControlUnit`**: precompute the fire-control-quality sensor
  sublist once in `__init__`; skip a threat entirely in `update()` once
  it's both cued and tracked — there's nothing left to determine about it.
- **`Simulation.run()`**: compute each active threat's position once per
  tick and pass it into `c2.update(..., positions=reds_now)` instead of
  `CommandControlUnit` independently re-deriving the same position a few
  lines later. `update()` still recomputes positions itself if called
  without `positions=` (e.g. from a unit test that only has one red and
  isn't running inside a `Simulation`), so this is purely an optimization,
  not a behavior change to the public API.

## Results

[`benchmarks/bench_c2_update.py`](../benchmarks/bench_c2_update.py) keeps
the *original* implementations around as `NaiveRadarUnit` /
`NaiveCommandControlUnit` — not used anywhere in `msim` itself, only here
— so the comparison is a real, re-runnable, apples-to-apples benchmark
rather than a one-off before/after snapshot:

```
python -m benchmarks.bench_c2_update
```

| Scenario | Before (best of 5) | After (best of 5) | Speedup |
|---|---|---|---|
| 40 threats / 25 interceptors | 0.948s | 0.612s | **1.55x** |
| 100 threats / 60 interceptors | 2.378s | 1.575s | **1.51x** |

Speedup is consistent (~1.5x) across scale rather than growing with `n`,
which makes sense given the fixes: they remove a roughly constant
per-call overhead multiplier, not a term in the complexity itself. The
underlying loop is still `O((t_max/dt) * n_threats)` — fixed-timestep
polling, not event-driven — see the note below.

## Correctness

Every change here is behavior-preserving — same public API, same
sequencing, same intercept/leaker outcomes. Verified by:

- The full `tests/` suite (48 tests) passing unchanged before and after.
- `bench_c2_update.py`'s naive and optimized runs producing the same
  scenario outcome counts (it prints them; they match).

## A bigger lever I didn't pull: fixed-timestep polling vs. event-driven

All of the above optimizes *constant factors* inside a loop that's
fundamentally `O((t_max/dt) * n_threats)` — every threat gets touched
every tick, whether or not anything changed for it. At real
constellation scale (hundreds to thousands of tracked objects), that
polling structure — not any single function — becomes the actual limit.

Every state transition this simulation cares about (radar acquisition,
weapon-release timing, ground/target impact) already has an exact,
closed-form timestamp the moment a `Missile` is constructed
(`impact_time` is solved analytically, not discovered by sampling). The
one thing that doesn't — proximity-based intercept detection between two
independently moving points — is also the one thing fixed-timestep
sampling is arguably the wrong tool for regardless of scale: too coarse
a `dt` relative to closing speed can miss or mistime a real intercept
(the existing `intercept_radius` vs `dt` tuning in `tests/conftest.py`'s
`easy_intercept_sim` fixture documents exactly this tradeoff).

A proper fix isn't a faster inner loop — it's an event-driven redesign
(a priority queue of next-event timestamps, jumping the clock straight
to each one, with intercept geometry solved analytically or via local
root-finding instead of sampled) — which changes the complexity class,
not just the constant. Given the scope of everything else in this
project, I scoped this investigation to the *measurable, shippable*
optimization rather than a rewrite; the event-driven redesign is the
next thing I'd propose if this needed to scale another order of
magnitude.
