"""Unit conversion helpers.

Positions, ranges, and altitudes throughout msim's public API (unit
positions, radar range, intercept radius, max altitude) are nautical
miles; speeds are knots. Missile's internal physics stays in SI (meters,
m/s) since gravity is naturally expressed that way — these helpers convert
at the boundary where the unit classes talk to Missile.
"""

NM_TO_M = 1852.0
MPS_PER_KNOT = NM_TO_M / 3600.0  # 1 knot = 1 nautical mile per hour


def nm_to_m(nm):
    return nm * NM_TO_M


def m_to_nm(m):
    return m / NM_TO_M


def knots_to_mps(knots):
    return knots * MPS_PER_KNOT


def mps_to_knots(mps):
    return mps / MPS_PER_KNOT
