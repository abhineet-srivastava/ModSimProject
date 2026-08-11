"""Time-stepped engagement simulation tying multiple red and blue units
together. C2 fuses sensor contacts into tracks; each tracked threat gets
greedily assigned to the first available (uncommitted) blue TEL that can
compute a feasible intercept solution against it — a threat with no blue
TEL free to take it, or with no feasible solution from any available one,
simply flies until impact and leaks."""

import numpy as np

from .units import nm_to_m


class Simulation:
    def __init__(self, red_tels, blue_tels, c2, dt=0.05, t_max=600.0, intercept_radius=0.02, hva=None):
        self.red_tels = list(red_tels)
        self.blue_tels = list(blue_tels)
        self.c2 = c2
        self.hva = hva
        self.dt = dt
        self.t_max = t_max
        self.intercept_radius = intercept_radius  # nm

        self.history = []
        self.threat_status = {}  # red.name -> {outcome, intercept_time, intercept_point (m), interceptor}

    def run(self, red_launch_times=None, red_targets=None, lofted=True):
        n = len(self.red_tels)
        if red_launch_times is None:
            red_launch_times = [0.0] * n
        if red_targets is None:
            if self.hva is None:
                raise ValueError("red_targets is required when no hva is configured")
            red_targets = [self.hva.position] * n

        for red, launch_time, target in zip(self.red_tels, red_launch_times, red_targets):
            red.launch_at_target(target, launch_time, lofted=lofted)
            self.threat_status[red.name] = {
                "outcome": None,
                "intercept_time": None,
                "intercept_point": None,
                "interceptor": None,
            }

        available_blues = list(self.blue_tels)
        assigned_blue_of = {}        # red.name -> BlueTEL
        assignment_attempted = set()  # red.name

        t = 0.0
        while t <= self.t_max:
            # Compute each unresolved threat's position once per tick and
            # share it with C2 instead of each independently re-calling
            # Missile.position() for the same red at the same t — profiling
            # showed this redundant call pair as a meaningful share of
            # runtime at constellation scale. See docs/PERFORMANCE.md.
            reds_now = {}
            for red in self.red_tels:
                if self.threat_status[red.name]["outcome"] is not None:
                    continue
                if red.missile.is_active(t):
                    reds_now[red.name] = red.missile.position(t)

            self.c2.update(self.red_tels, t, positions=reds_now)

            for red in self.red_tels:
                status = self.threat_status[red.name]
                if status["outcome"] is not None or red.name in assignment_attempted:
                    continue
                detect_time = self.c2.tracks.get(red.missile)
                if detect_time is None or t < detect_time:
                    continue
                assignment_attempted.add(red.name)
                for blue in available_blues:
                    if blue.compute_intercept(red.missile, detect_time) is not None:
                        status["interceptor"] = blue.name
                        assigned_blue_of[red.name] = blue
                        available_blues.remove(blue)
                        break

            for blue in assigned_blue_of.values():
                if (blue.interceptor is None and blue.intercept_solution is not None
                        and t >= blue.intercept_solution[0]):
                    blue.launch_interceptor()

            # A blue whose assigned threat has already been intercepted has
            # itself collided at that moment — its Missile object doesn't
            # know that and would otherwise keep flying its programmed
            # parabola, so stop rendering it past its own kill.
            red_of_blue = {blue.name: red_name for red_name, blue in assigned_blue_of.items()}
            blues_now = {}
            for blue in self.blue_tels:
                if blue.interceptor is None or not blue.interceptor.is_active(t):
                    continue
                assigned_red = red_of_blue.get(blue.name)
                if assigned_red is not None:
                    rstatus = self.threat_status[assigned_red]
                    if rstatus["outcome"] == "INTERCEPT" and t > rstatus["intercept_time"]:
                        continue
                blues_now[blue.name] = blue.interceptor.position(t)

            self.history.append({"t": t, "reds": reds_now, "blues": blues_now})

            for red_name, red_pos in reds_now.items():
                blue = assigned_blue_of.get(red_name)
                if blue is None or blue.name not in blues_now:
                    continue
                blue_pos = blues_now[blue.name]
                if np.linalg.norm(red_pos - blue_pos) <= nm_to_m(self.intercept_radius):
                    status = self.threat_status[red_name]
                    status["outcome"] = "INTERCEPT"
                    status["intercept_time"] = t
                    status["intercept_point"] = (red_pos + blue_pos) / 2

            for red in self.red_tels:
                status = self.threat_status[red.name]
                if status["outcome"] is None and t >= red.missile.impact_time:
                    status["outcome"] = "LEAKER"

            if all(s["outcome"] is not None for s in self.threat_status.values()):
                break

            t += self.dt

        return self.threat_status
