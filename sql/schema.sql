-- Schema for persisting missile-defense engagement simulation runs.
--
-- Written against the standard PostgreSQL wire protocol. CockroachDB
-- speaks the same protocol and supports everything used here (SERIAL,
-- TIMESTAMPTZ, FK constraints, standard indexes), so this schema and
-- msim/db.py work unmodified against either.

CREATE TABLE IF NOT EXISTS runs (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    dt_seconds          DOUBLE PRECISION NOT NULL,
    t_max_seconds       DOUBLE PRECISION NOT NULL,
    intercept_radius_nm DOUBLE PRECISION NOT NULL,
    hva_name            TEXT,
    hva_x_nm            DOUBLE PRECISION,
    hva_y_nm            DOUBLE PRECISION,
    threat_count        INTEGER NOT NULL,
    interceptor_count   INTEGER NOT NULL,
    intercept_count     INTEGER NOT NULL,
    leaker_count        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS threats (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              BIGINT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    launch_x_nm         DOUBLE PRECISION NOT NULL,
    launch_y_nm         DOUBLE PRECISION NOT NULL,
    lateral_offset_nm   DOUBLE PRECISION NOT NULL,
    speed_kn            DOUBLE PRECISION,
    launch_angle_deg    DOUBLE PRECISION,
    launch_time_s       DOUBLE PRECISION NOT NULL,
    impact_time_s       DOUBLE PRECISION NOT NULL,
    cue_time_s          DOUBLE PRECISION,
    detect_time_s       DOUBLE PRECISION,
    outcome             TEXT NOT NULL,
    intercept_time_s    DOUBLE PRECISION,
    intercept_x_nm      DOUBLE PRECISION,
    intercept_y_nm      DOUBLE PRECISION,
    interceptor_name    TEXT
);

CREATE TABLE IF NOT EXISTS interceptors (
    id                  BIGSERIAL PRIMARY KEY,
    run_id              BIGINT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    position_x_nm       DOUBLE PRECISION NOT NULL,
    position_y_nm       DOUBLE PRECISION NOT NULL,
    speed_kn            DOUBLE PRECISION NOT NULL,
    launch_time_s       DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_threats_run_id ON threats(run_id);
CREATE INDEX IF NOT EXISTS idx_interceptors_run_id ON interceptors(run_id);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
