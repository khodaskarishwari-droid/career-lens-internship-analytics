from datetime import date, timedelta
import pandas as pd

from app import (
    COLUMNS, STATUSES, calculate_metrics, calculate_skill_match,
    generate_id, parse_skills, skill_frequency, upcoming_followups, validate_data
)


def test_parse_skills_removes_blanks_and_duplicates():
    assert parse_skills("Python, SQL, python, , SQL ") == ["Python", "SQL"]


def test_skill_match_case_insensitive_and_empty_requirements():
    result = calculate_skill_match(["python", "SQL"], "Python, SQL, Pandas")
    assert result["matched"] == ["Python", "SQL"]
    assert result["missing"] == ["Pandas"]
    assert result["score"] == 2 / 3
    assert calculate_skill_match(["Python"], "")["score"] == 0.0


def test_metrics_empty_dataframe():
    empty = pd.DataFrame(columns=COLUMNS)
    result = calculate_metrics(empty)
    assert result["total"] == 0
    assert result["offer_rate"] == 0.0
    assert result["response_rate"] == 0.0


def test_metrics_counts_statuses():
    frame = pd.DataFrame([
        ["1", "A", "Analyst", "Applied", "", "", "", "", ""],
        ["2", "B", "Analyst", "Interview", "", "", "", "", ""],
        ["3", "C", "Analyst", "Offer", "", "", "", "", ""],
    ], columns=COLUMNS)
    result = calculate_metrics(frame)
    assert result["total"] == 3
    assert result["interviews"] == 1
    assert result["offers"] == 1
    assert result["offer_rate"] == 100 / 3


def test_validate_data_adds_columns_and_drops_missing_company_role():
    frame = pd.DataFrame([{"Company": " A ", "Role": "Analyst", "Status": "Unknown"},
                          {"Company": "", "Role": "Missing company", "Status": "Applied"}])
    clean = validate_data(frame)
    assert list(clean.columns) == COLUMNS
    assert len(clean) == 1
    assert clean.iloc[0]["Company"] == "A"
    assert clean.iloc[0]["Status"] == "Interested"


def test_generate_id_avoids_existing_ids():
    frame = pd.DataFrame({"ID": ["CL-1001", "CL-1002"]})
    assert generate_id(frame) == "CL-1003"


def test_skill_frequency_counts_once_per_record():
    frame = pd.DataFrame({"Required Skills": ["Python, SQL, python", "SQL, Excel"]})
    result = skill_frequency(frame).set_index("Skill")["Opportunities"].to_dict()
    assert result["Python"] == 1
    assert result["SQL"] == 2
    assert result["Excel"] == 1


def test_upcoming_followups_only_open_and_due():
    today = date(2026, 10, 23)
    frame = pd.DataFrame([
        ["1", "A", "Analyst", "Applied", "", "2026-10-01", "2026-10-22", "", ""],
        ["2", "B", "Analyst", "Offer", "", "2026-10-01", "2026-10-22", "", ""],
        ["3", "C", "Analyst", "Applied", "", "2026-10-01", "2026-10-30", "", ""],
    ], columns=COLUMNS)
    due = upcoming_followups(frame, today=today)
    assert due["ID"].tolist() == ["1"]
