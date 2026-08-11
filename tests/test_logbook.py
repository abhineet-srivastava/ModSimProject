"""msim.logbook: CSV logbooks (runs.csv / threats.csv / sensors.csv),
append-only across multiple runs, header written exactly once per file."""

import csv

from msim.logbook import append_run


def _read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_first_append_creates_all_three_files_with_correct_rows(tmp_path, easy_intercept_sim):
    easy_intercept_sim.run(lofted=False)
    logbook_dir = tmp_path / "logbook"
    run_timestamp = append_run(easy_intercept_sim, logbook_dir=logbook_dir)

    runs = _read_csv(logbook_dir / "runs.csv")
    threats = _read_csv(logbook_dir / "threats.csv")
    sensors = _read_csv(logbook_dir / "sensors.csv")

    assert len(runs) == 1
    assert runs[0]["run_timestamp"] == run_timestamp
    assert runs[0]["threat_count"] == "1"
    assert runs[0]["interceptor_count"] == "1"
    assert runs[0]["intercept_count"] == "1"
    assert runs[0]["leaker_count"] == "0"

    assert len(threats) == 1
    assert threats[0]["name"] == "RED-TEST"
    assert threats[0]["outcome"] == "INTERCEPT"
    assert threats[0]["interceptor_name"] == "BLUE-TEST"

    assert len(sensors) == 1
    assert sensors[0]["name"] == "RADAR-TEST"
    assert sensors[0]["sensor_type"] == "radar"
    assert float(sensors[0]["detection_range_nm"]) == 15.0


def test_second_append_adds_rows_without_duplicating_header(tmp_path, easy_intercept_sim, guaranteed_leaker_sim):
    logbook_dir = tmp_path / "logbook"

    easy_intercept_sim.run(lofted=False)
    append_run(easy_intercept_sim, logbook_dir=logbook_dir)

    guaranteed_leaker_sim.run(lofted=False)
    append_run(guaranteed_leaker_sim, logbook_dir=logbook_dir)

    runs = _read_csv(logbook_dir / "runs.csv")
    threats = _read_csv(logbook_dir / "threats.csv")

    assert len(runs) == 2
    assert len(threats) == 2
    assert threats[0]["outcome"] == "INTERCEPT"
    assert threats[1]["outcome"] == "LEAKER"

    # only one header line in each file, not one per append
    header_line = "run_timestamp"
    with (logbook_dir / "runs.csv").open(encoding="utf-8") as f:
        contents = f.read()
    assert contents.count(header_line) == 1


def test_satellite_sensor_has_null_detection_range(tmp_path, hva, c2_with_satellite):
    from msim import RedTEL, Simulation

    red = RedTEL("RED-TEST", position=(0.0, 0.0), speed=1500.0)
    sim = Simulation([red], [], c2_with_satellite, dt=0.1, t_max=200.0, intercept_radius=1.0, hva=hva)
    sim.run(lofted=False)

    logbook_dir = tmp_path / "logbook"
    append_run(sim, logbook_dir=logbook_dir)

    sensors = {row["name"]: row for row in _read_csv(logbook_dir / "sensors.csv")}
    assert sensors["SAT-TEST"]["sensor_type"] == "satellite"
    assert sensors["SAT-TEST"]["detection_range_nm"] == ""
    assert float(sensors["RADAR-TEST"]["detection_range_nm"]) == 15.0


def test_leaker_threat_row_has_empty_intercept_fields(tmp_path, guaranteed_leaker_sim):
    guaranteed_leaker_sim.run(lofted=False)
    logbook_dir = tmp_path / "logbook"
    append_run(guaranteed_leaker_sim, logbook_dir=logbook_dir)

    threats = _read_csv(logbook_dir / "threats.csv")
    assert threats[0]["outcome"] == "LEAKER"
    assert threats[0]["intercept_time_s"] == ""
    assert threats[0]["intercept_x_nm"] == ""
    assert threats[0]["interceptor_name"] == ""
