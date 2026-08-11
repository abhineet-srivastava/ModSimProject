"""Red force unit classes."""

import numpy as np

from .missile import Missile
from .units import nm_to_m, knots_to_mps, mps_to_knots


class RedTEL:
    """Launches a ballistic threat missile on a parabolic trajectory aimed
    at a target location. Position is nautical miles, speed is knots.

    If `max_altitude` (nautical miles) is set, launches are solved to hit
    the target at exactly that apex height — the launch speed is then a
    *derived* result (overwriting `self.speed`) rather than the configured
    one. Leave it `None` to fly at the configured `speed` instead, in which
    case the launch angle is solved to hit the target at that speed.

    `lateral_offset` (nautical miles) is display-only: it says how far to
    the side of the main range axis this TEL's launch site sits (e.g. a
    dispersed battery firing from different bearings toward the same
    target), for the 3D viewer to place it accurately. The ballistic solve
    itself stays two-dimensional (straight-line range + altitude) and does
    not use it — every TEL still aims at the same target position
    regardless of its lateral offset."""

    def __init__(self, name, position, speed=None, max_altitude=None, lateral_offset=0.0, gravity=9.81):
        self.name = name
        self.position = np.array(position, dtype=float)  # nm
        self.speed = speed  # knots
        self.max_altitude = max_altitude  # nm, optional
        self.lateral_offset = lateral_offset  # nm, display-only
        self.gravity = gravity  # m/s^2 — a physical constant, not a display unit
        self.missile = None
        self.target = None
        self.launch_angle = None

    def launch(self, speed_knots, angle_deg, launch_time):
        speed_mps = knots_to_mps(speed_knots)
        angle = np.radians(angle_deg)
        velocity = (speed_mps * np.cos(angle), speed_mps * np.sin(angle))
        self.missile = Missile(
            name=f"{self.name}-TBM",
            launch_pos=nm_to_m(self.position),
            velocity=velocity,
            launch_time=launch_time,
            gravity=self.gravity,
        )
        return self.missile

    def compute_launch_angle(self, target_pos, speed_knots, lofted=True):
        """Solve the launch angle (degrees) that lands a shot fired at
        `speed_knots` exactly on target_pos (nm), via the ballistic range
        equation y = x*tan(theta) - g*x^2 / (2*v^2*cos^2(theta)), solved for
        theta by substituting u = tan(theta) and treating it as a quadratic
        in u. Returns the lofted (high-angle) solution by default; there
        are generally two angles that hit a given point at a fixed speed."""
        target_m = nm_to_m(np.asarray(target_pos, dtype=float))
        origin_m = nm_to_m(self.position)
        dx = target_m[0] - origin_m[0]
        dy = target_m[1] - origin_m[1]
        v = knots_to_mps(speed_knots)
        g = self.gravity

        a = g * dx ** 2 / (2 * v ** 2)
        b = -dx
        c = dy + a
        disc = b ** 2 - 4 * a * c
        if disc < 0:
            raise ValueError(
                f"{self.name}: target at offset ({dx:.0f}, {dy:.0f}) m is out of range at speed={speed_knots} kn"
            )

        sqrt_disc = np.sqrt(disc)
        u1 = (-b + sqrt_disc) / (2 * a)
        u2 = (-b - sqrt_disc) / (2 * a)
        angle1, angle2 = np.degrees(np.arctan(u1)), np.degrees(np.arctan(u2))
        return max(angle1, angle2) if lofted else min(angle1, angle2)

    def compute_apex_solution(self, target_pos, max_altitude):
        """Solve (speed_knots, angle_deg) so the trajectory both reaches
        target_pos (nm) and peaks at exactly max_altitude (nm).

        The apex height alone fixes the vertical launch speed vy (apex =
        vy^2 / 2g). That, together with the target's altitude, fixes the
        total time of flight (same quadratic Missile uses to find when a
        trajectory returns to a given altitude). The horizontal speed vx
        is then whatever covers the horizontal distance in that time."""
        target_m = nm_to_m(np.asarray(target_pos, dtype=float))
        origin_m = nm_to_m(self.position)
        y0 = origin_m[1]
        apex_m = nm_to_m(max_altitude)
        g = self.gravity

        if apex_m < y0:
            raise ValueError(f"{self.name}: max_altitude must be at or above the launch altitude")
        if apex_m < target_m[1]:
            raise ValueError(f"{self.name}: max_altitude must be at or above the target's altitude")

        vy = np.sqrt(2 * g * (apex_m - y0))

        a = -0.5 * g
        b = vy
        c = y0 - target_m[1]
        disc = b ** 2 - 4 * a * c
        sqrt_disc = np.sqrt(disc)
        t1 = (-b + sqrt_disc) / (2 * a)
        t2 = (-b - sqrt_disc) / (2 * a)
        tof = max(t1, t2)

        dx = target_m[0] - origin_m[0]
        vx = dx / tof
        speed_mps = np.hypot(vx, vy)
        angle_deg = np.degrees(np.arctan2(vy, vx))
        return mps_to_knots(speed_mps), angle_deg

    def launch_at_target(self, target_pos, launch_time, lofted=True):
        """Aim at target_pos (nm) using self.max_altitude if set, else
        self.speed. Updates self.speed and self.launch_angle either way,
        so both reflect what actually flew."""
        target_pos = np.asarray(target_pos, dtype=float)
        if self.max_altitude is not None:
            speed, angle = self.compute_apex_solution(target_pos, self.max_altitude)
        else:
            if self.speed is None:
                raise ValueError(f"{self.name}: either speed or max_altitude must be set")
            speed = self.speed
            angle = self.compute_launch_angle(target_pos, speed, lofted=lofted)

        self.target = target_pos
        self.speed = speed
        self.launch_angle = angle
        return self.launch(speed, angle, launch_time)
