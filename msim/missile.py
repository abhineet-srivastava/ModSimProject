"""Ballistic flight-body model shared by threat missiles and interceptors."""

import numpy as np


class Missile:
    """A body in unpowered parabolic flight under constant gravity."""

    def __init__(self, name, launch_pos, velocity, launch_time, gravity=9.81):
        self.name = name
        self.launch_pos = np.array(launch_pos, dtype=float)
        self.velocity = np.array(velocity, dtype=float)
        self.launch_time = launch_time
        self.gravity = gravity
        self.impact_time = self._compute_impact_time()

    def _compute_impact_time(self):
        y0 = self.launch_pos[1]
        vy = self.velocity[1]
        g = self.gravity
        a, b, c = -0.5 * g, vy, y0
        disc = b ** 2 - 4 * a * c
        if disc < 0:
            return self.launch_time
        t1 = (-b + np.sqrt(disc)) / (2 * a)
        t2 = (-b - np.sqrt(disc)) / (2 * a)
        return self.launch_time + max(t1, t2)

    def position(self, t):
        """Position at time t, clamped to ground once past impact time."""
        if t < self.launch_time:
            return None
        dt = min(t, self.impact_time) - self.launch_time
        x0, y0 = self.launch_pos
        vx, vy = self.velocity
        g = self.gravity
        x = x0 + vx * dt
        y = y0 + vy * dt - 0.5 * g * dt ** 2
        return np.array([x, max(y, 0.0)])

    def is_active(self, t):
        return self.launch_time <= t <= self.impact_time
