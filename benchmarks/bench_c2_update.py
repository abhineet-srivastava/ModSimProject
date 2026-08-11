"""Reproducible before/after benchmark for the CommandControlUnit /
RadarUnit optimizations described in docs/PERFORMANCE.md.

The "naive" classes below are the original implementations, kept here
only as a benchmarking baseline (not used anywhere in msim itself) so the
improvement has an honest, runnable comparison rather than a one-off
before/after cProfile snapshot that can't be re-verified later.
"""

import time

import numpy as np

from benchmarks.stress_scenario import build_stress_scenario
from msim.units import nm_to_m


class NaiveRadarUnit:
    """The original RadarUnit.in_range: reconverts its own constant
    position/range from nm to meters on every single call."""

    fire_control_quality = True

    def __init__(self, name, position, detection_range):
        self.name = name
        self.position = np.array(position, dtype=float)
        self.detection_range = detection_range

    def in_range(self, target_pos_m):
        if target_pos_m is None:
            return False
        d_m = np.linalg.norm(np.asarray(target_pos_m, dtype=float) - nm_to_m(self.position))
        return d_m <= nm_to_m(self.detection_range)


class NaiveCommandControlUnit:
    """The original CommandControlUnit.update: no early-exit for already
    fully-resolved threats, no shared positions with Simulation.run(),
    rebuilds the fire-control-sensor sublist every call."""

    def __init__(self, name, position, sensors, detection_delay=1.0, cue_delay=0.5):
        self.name = name
        self.position = np.array(position, dtype=float)
        self.sensors = list(sensors)
        self.detection_delay = detection_delay
        self.cue_delay = cue_delay
        self.cues = {}
        self.tracks = {}

    def update(self, red_tels, current_time, positions=None):
        # `positions` accepted-but-ignored: Simulation.run() always passes
        # it now, and this baseline intentionally represents the *original*
        # per-call behavior (independently re-fetching position itself)
        # rather than a partial hybrid.
        fc_sensors = [s for s in self.sensors if s.fire_control_quality]
        for red_tel in red_tels:
            missile = red_tel.missile
            if missile is None:
                continue
            pos = missile.position(current_time) if missile.is_active(current_time) else None
            if pos is None:
                continue
            if missile not in self.cues and any(s.in_range(pos) for s in self.sensors):
                self.cues[missile] = current_time + self.cue_delay
            if missile not in self.tracks and any(s.in_range(pos) for s in fc_sensors):
                self.tracks[missile] = current_time + self.detection_delay


def _swap_c2(sim, naive):
    """Rebuild sim.c2 as either the naive or the current CommandControlUnit,
    wrapping its sensors in the matching RadarUnit variant, then re-point
    every red/blue's references so behavior is otherwise identical."""
    from msim import CommandControlUnit, RadarUnit

    old_c2 = sim.c2
    sensor_cls = NaiveRadarUnit if naive else RadarUnit
    new_sensors = [
        sensor_cls(s.name, s.position, s.detection_range) if hasattr(s, "detection_range") else s
        for s in old_c2.sensors
    ]
    c2_cls = NaiveCommandControlUnit if naive else CommandControlUnit
    sim.c2 = c2_cls(old_c2.name, old_c2.position, new_sensors,
                     detection_delay=old_c2.detection_delay, cue_delay=old_c2.cue_delay)


def bench(naive, n_reds=40, n_blues=25, trials=5):
    times = []
    for _ in range(trials):
        sim, launch_times = build_stress_scenario(n_reds, n_blues)
        _swap_c2(sim, naive)
        t0 = time.perf_counter()
        sim.run(red_launch_times=launch_times, lofted=False)
        times.append(time.perf_counter() - t0)
    return times


def main():
    print("Constellation-scale benchmark: 40 threats, 25 interceptors, 5 trials each\n")

    naive_times = bench(naive=True)
    print(f"BEFORE (naive C2.update + RadarUnit): {[round(t, 3) for t in naive_times]}")
    print(f"  best: {min(naive_times):.3f}s   mean: {sum(naive_times)/len(naive_times):.3f}s\n")

    fast_times = bench(naive=False)
    print(f"AFTER  (optimized):                   {[round(t, 3) for t in fast_times]}")
    print(f"  best: {min(fast_times):.3f}s   mean: {sum(fast_times)/len(fast_times):.3f}s\n")

    speedup = min(naive_times) / min(fast_times)
    print(f"speedup: {speedup:.2f}x (best-of-{len(naive_times)})")


if __name__ == "__main__":
    main()
