"""Database persistence tests. Require a live PostgreSQL/CockroachDB
instance reachable via DATABASE_URL — skipped entirely otherwise (e.g. a
laptop with no local Postgres running). CI provides a real Postgres
service container so these actually run there; see
.github/workflows/ci.yml.
"""

import os

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from msim import db  # noqa: E402  (import after importorskip is intentional)

DATABASE_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")


class _TrackedConnection:
    """Wraps a psycopg2 connection with a list of run ids to clean up
    afterward. psycopg2's connection is a C extension type that doesn't
    support attaching arbitrary attributes directly, hence the wrapper
    rather than just stashing state on the connection object."""

    def __init__(self, connection):
        self.connection = connection
        self.inserted_run_ids = []

    def save(self, sim):
        run_id = db.save_run(self.connection, sim)
        self.inserted_run_ids.append(run_id)
        return run_id


@pytest.fixture
def conn():
    connection = db.get_connection()
    db.init_schema(connection)
    tracked = _TrackedConnection(connection)
    yield tracked
    with connection.cursor() as cur:
        for run_id in tracked.inserted_run_ids:
            cur.execute("DELETE FROM runs WHERE id = %s", (run_id,))  # cascades
    connection.commit()
    connection.close()


def test_save_and_fetch_run_detail(conn, easy_intercept_sim):
    easy_intercept_sim.run(lofted=False)
    run_id = conn.save(easy_intercept_sim)

    detail = db.fetch_run_detail(conn.connection, run_id)
    assert detail["run"]["threat_count"] == 1
    assert detail["run"]["interceptor_count"] == 1
    assert detail["run"]["intercept_count"] == 1
    assert len(detail["threats"]) == 1
    assert detail["threats"][0]["name"] == "RED-TEST"
    assert detail["threats"][0]["outcome"] == "INTERCEPT"
    assert detail["threats"][0]["interceptor_name"] == "BLUE-TEST"
    assert len(detail["interceptors"]) == 1
    assert detail["interceptors"][0]["name"] == "BLUE-TEST"


def test_fetch_run_detail_missing_run_returns_none(conn):
    assert db.fetch_run_detail(conn.connection, run_id=-1) is None


def test_leaker_run_persists_null_intercept_fields(conn, guaranteed_leaker_sim):
    guaranteed_leaker_sim.run(lofted=False)
    run_id = conn.save(guaranteed_leaker_sim)

    detail = db.fetch_run_detail(conn.connection, run_id)
    threat = detail["threats"][0]
    assert threat["outcome"] == "LEAKER"
    assert threat["intercept_time_s"] is None
    assert threat["intercept_x_nm"] is None
    assert threat["interceptor_name"] is None


def test_fetch_recent_runs_orders_newest_first(conn, easy_intercept_sim):
    easy_intercept_sim.run(lofted=False)
    first_id = conn.save(easy_intercept_sim)

    easy_intercept_sim.history = []
    easy_intercept_sim.threat_status = {}
    easy_intercept_sim.run(lofted=False)
    second_id = conn.save(easy_intercept_sim)

    recent = db.fetch_recent_runs(conn.connection, limit=2)
    ids = [row["id"] for row in recent]
    assert ids.index(second_id) < ids.index(first_id)
