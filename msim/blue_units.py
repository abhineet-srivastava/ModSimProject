"""Blue force unit classes: sensors (ground radar + space-based),
command and control, interceptor launchers, and the high-value asset the
whole battery is defending. Position is nautical miles, speed is knots
throughout."""

import numpy as np

from .missile import Missile
from .units import nm_to_m, knots_to_mps


class RadarUnit:
    """A ground radar site with a simple range-based sensor volume: a
    target is detectable once it comes within `detection_range` (nm) of
    this radar — coverage is local and closing-range gated."""

    fire_control_quality = True  # precise enough to hand a weapon a firing solution

    def __init__(self, name, position, detection_range):
        self.name = name
        self.position = np.array(position, dtype=float)  # nm
        self.detection_range = detection_range  # nm
        # position/range never change after construction — converting them
        # to meters once here (instead of on every in_range() call, which
        # profiling showed happening hundreds of thousands of times over a
        # constellation-scale run) avoids reconverting the same constants
        # on every tick. See docs/PERFORMANCE.md.
        self._position_m = nm_to_m(self.position)
        self._range_m = nm_to_m(self.detection_range)

    def in_range(self, target_pos_m):
        """target_pos_m is a Missile-native position, in meters."""
        if target_pos_m is None:
            return False
        d_m = np.linalg.norm(np.asarray(target_pos_m, dtype=float) - self._position_m)
        return d_m <= self._range_m


class SatelliteUnit:
    """A space-based early-warning sensor (e.g. an SBIRS-style overhead
    IR tracker): unlike ground radar it isn't range-gated — it sees a
    threat's boost/flight plume from orbit the moment it's airborne,
    anywhere in theater, and keeps tracking it for the rest of its flight.
    `position` is display-only (where its icon sits in the 3D scene, e.g.
    a nominal altitude/downrange point) and plays no role in detection.

    Coarse cueing only: real overhead IR sensors localize a launch well
    enough to alert and roughly cross-cue a search, but not precisely
    enough to hand a weapon a firing solution — that still requires a
    radar (or other `fire_control_quality` sensor) to pick the target up
    directly. See CommandControlUnit."""

    fire_control_quality = False

    def __init__(self, name, position):
        self.name = name
        self.position = np.array(position, dtype=float)  # nm, display-only

    def in_range(self, target_pos_m):
        return target_pos_m is not None


class CommandControlUnit:
    """Fuses contacts from any number of sensors (radar, satellite, ...)
    into two tiers of confirmation, each with its own correlation delay:

    - `cues`: a coarse early-warning contact from *any* sensor (including
      a satellite) — enough to alert, not enough to shoot.
    - `tracks`: a fire-control-quality contact from a sensor that can
      actually support a firing solution (`sensor.fire_control_quality`,
      true for RadarUnit, false for SatelliteUnit). Blue force units only
      act on `tracks`.

    Tracks multiple simultaneous threats."""

    def __init__(self, name, position, sensors, detection_delay=1.0, cue_delay=0.5):
        self.name = name
        self.position = np.array(position, dtype=float)  # nm
        self.sensors = list(sensors)
        self._fc_sensors = [s for s in self.sensors if s.fire_control_quality]
        self.detection_delay = detection_delay  # correlation delay for a fire-control-quality track
        self.cue_delay = cue_delay              # correlation delay for a coarse early-warning cue
        self.cues = {}    # missile -> cue_time (any sensor)
        self.tracks = {}  # missile -> detect_time (fire-control-quality sensor only)

    def update(self, red_tels, current_time, positions=None):
        """Update cues/tracks for every red TEL's missile.

        `positions` is an optional {red.name: meters-position} map for
        currently-active threats (Simulation.run() already computes this
        once per tick for its own history bookkeeping); when given, it's
        reused instead of each threat independently re-calling
        Missile.position() for the same instant. Falls back to computing
        positions itself if not given, e.g. for standalone/test use.

        Skips any missile already fully resolved (both cued and tracked)
        — profiling a constellation-scale run showed this loop
        re-evaluating sensor range against already-tracked threats for the
        rest of their flight was a meaningful share of runtime. See
        docs/PERFORMANCE.md."""
        for red_tel in red_tels:
            missile = red_tel.missile
            if missile is None or (missile in self.cues and missile in self.tracks):
                continue
            if positions is not None:
                pos = positions.get(red_tel.name)
            else:
                pos = missile.position(current_time) if missile.is_active(current_time) else None
            if pos is None:
                continue
            if missile not in self.cues and any(s.in_range(pos) for s in self.sensors):
                self.cues[missile] = current_time + self.cue_delay
            if missile not in self.tracks and any(s.in_range(pos) for s in self._fc_sensors):
                self.tracks[missile] = current_time + self.detection_delay
        return self.tracks


class BlueTEL:
    """Computes a predicted-intercept-point solution against a tracked
    threat and launches an interceptor to meet it there. Single-shot: one
    BlueTEL commits to at most one target."""

    def __init__(self, name, position, speed, reaction_delay=2.0, gravity=9.81):
        self.name = name
        self.position = np.array(position, dtype=float)  # nm
        self.speed = speed  # knots — this interceptor's max deliverable speed
        self.reaction_delay = reaction_delay
        self.gravity = gravity
        self.interceptor = None
        self.intercept_solution = None  # (launch_time, target_point_m, tof, velocity_mps)

    def compute_intercept(self, threat, detect_time, tof_step=0.05):
        """Search forward in time-of-flight for the earliest point along the
        threat's known trajectory this TEL's interceptor can reach."""
        g = self.gravity
        launch_time = detect_time + self.reaction_delay
        origin_m = nm_to_m(self.position)
        speed_mps = knots_to_mps(self.speed)

        tof = tof_step
        while launch_time + tof <= threat.impact_time:
            target = threat.position(launch_time + tof)  # meters, Missile-native
            if target is not None:
                dx = target[0] - origin_m[0]
                dy = target[1] - origin_m[1]
                vx = dx / tof
                vy = (dy + 0.5 * g * tof ** 2) / tof
                speed_needed = np.hypot(vx, vy)
                if speed_needed <= speed_mps:
                    self.intercept_solution = (launch_time, target, tof, (vx, vy))
                    return self.intercept_solution
            tof += tof_step

        self.intercept_solution = None
        return None

    def launch_interceptor(self):
        if not self.intercept_solution:
            return None
        launch_time, _target, _tof, velocity = self.intercept_solution
        self.interceptor = Missile(
            name=f"{self.name}-Interceptor",
            launch_pos=nm_to_m(self.position),
            velocity=velocity,
            launch_time=launch_time,
            gravity=self.gravity,
        )
        return self.interceptor


class HighValueAsset:
    """A stationary ground site (altitude 0) that the blue force is
    defending; the target the red threats are aimed at. Position is nm."""

    def __init__(self, name, position):
        self.name = name
        self.position = np.array(position, dtype=float)  # nm
