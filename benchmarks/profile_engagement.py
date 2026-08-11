"""Profile Simulation.run() on a constellation-scale scenario with
cProfile and print the hottest functions by cumulative time.

Usage: python -m benchmarks.profile_engagement [n_reds] [n_blues]
"""

import cProfile
import pstats
import sys

from benchmarks.stress_scenario import build_stress_scenario


def main():
    n_reds = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    n_blues = int(sys.argv[2]) if len(sys.argv) > 2 else 25

    sim, launch_times = build_stress_scenario(n_reds, n_blues)

    profiler = cProfile.Profile()
    profiler.enable()
    status = sim.run(red_launch_times=launch_times, lofted=False)
    profiler.disable()

    intercepts = sum(1 for s in status.values() if s["outcome"] == "INTERCEPT")
    leakers = sum(1 for s in status.values() if s["outcome"] == "LEAKER")
    print(f"scenario: {n_reds} reds, {n_blues} blues -> {intercepts} INTERCEPT / {leakers} LEAKER")
    print(f"history frames recorded: {len(sim.history)}")
    print()

    stats = pstats.Stats(profiler).sort_stats("cumulative")
    stats.print_stats(15)


if __name__ == "__main__":
    main()
