import json
from pathlib import Path

import pytest

from ds_finance_concept.metric_series.builder import build_metric_series
from ds_finance_concept.metric_series.errors import CandidateValidationError, ReviewDecisionError
from ds_finance_concept.metric_series.schema import parse_period


def make_candidate(overrides=None):
    d = {
        "candidate_id": "mc_001",
        "metric_id": "revenue",
        "metric_name": "营业收入",
        "report_period": "2024Q1",
        "value_normalized": 12345600.0,
        "value_unit_normalized": "CNY",
        "is_percent": False,
        "confidence": "high",
        "needs_review": False,
        "source_pdf": "2024Q1.pdf",
        "page_number": 5,
        "source_snippet": "营业收入 1,234.56 万元",
        "raw_value": "1,234.56 万元",
        "value": 1234.56,
    }
    if overrides:
        d.update(overrides)
    return d


def _write_candidates(path: Path, items: list[dict]) -> None:
    lines = [json.dumps(i, ensure_ascii=False) for i in items]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_empty_candidates(tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text("", encoding="utf-8")
    groups, series, _ = build_metric_series(f)
    assert groups == []
    assert series == []


def test_bad_json_fails(tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text("not json\n", encoding="utf-8")
    with pytest.raises(CandidateValidationError):
        build_metric_series(f)


def test_missing_field_fails(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [{"candidate_id": "mc_1", "metric_id": "revenue"}])
    with pytest.raises(CandidateValidationError):
        build_metric_series(f)


def test_duplicate_id_different_content_fails(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [
        make_candidate({"candidate_id": "mc_dup", "value_normalized": 100}),
        make_candidate({"candidate_id": "mc_dup", "value_normalized": 200}),
    ])
    with pytest.raises(CandidateValidationError, match="different content"):
        build_metric_series(f)


def test_duplicate_id_same_content_ok(tmp_path):
    f = tmp_path / "c.jsonl"
    c = make_candidate()
    _write_candidates(f, [c, c])
    groups, series, warnings = build_metric_series(f)
    assert len(groups) == 1
    assert groups[0].status == "selected"
    assert warnings


def test_high_confidence_auto_selected(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate()])
    groups, series, _ = build_metric_series(f)
    assert len(groups) == 1
    assert groups[0].status == "selected"
    assert groups[0].selection_method == "auto_unique"
    assert len(series) == 1


def test_medium_confidence_auto_selected(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate({"confidence": "medium"})])
    groups, series, _ = build_metric_series(f)
    assert groups[0].status == "selected"


def test_low_confidence_review_queue(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate({"confidence": "low"})])
    groups, series, _ = build_metric_series(f)
    assert groups[0].status == "needs_review"
    assert series == []


def test_needs_review_review_queue(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate({"needs_review": True})])
    groups, series, _ = build_metric_series(f)
    assert groups[0].status == "needs_review"


def test_unknown_period_review_queue(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate({"report_period": "unknown"})])
    groups, series, _ = build_metric_series(f)
    assert groups[0].status == "needs_review"


def test_unknown_unit_review_queue(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate({"value_unit_normalized": "unknown"})])
    groups, series, _ = build_metric_series(f)
    assert groups[0].status == "needs_review"


def test_gross_margin_non_percent_review(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate({
        "metric_id": "gross_margin",
        "metric_name": "毛利率",
        "is_percent": False,
    })])
    groups, series, _ = build_metric_series(f)
    assert groups[0].status == "needs_review"


def test_multi_same_value_selected(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [
        make_candidate({"candidate_id": "mc_a"}),
        make_candidate({"candidate_id": "mc_b"}),
    ])
    groups, series, _ = build_metric_series(f)
    assert groups[0].status == "selected"


def test_multi_diff_value_conflict(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [
        make_candidate({"candidate_id": "mc_a", "value_normalized": 100000000, "value_unit_normalized": "CNY"}),
        make_candidate({"candidate_id": "mc_b", "value_normalized": 200000000, "value_unit_normalized": "CNY"}),
    ])
    groups, series, _ = build_metric_series(f)
    assert groups[0].status == "conflict"


def test_review_approve(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate({"confidence": "low"})])

    dec = tmp_path / "dec.csv"
    dec.write_text("candidate_id,decision,reviewer_note\nmc_001,approve,ok\n", encoding="utf-8")

    groups, series, warnings = build_metric_series(f, dec)
    assert groups[0].status == "selected"
    assert groups[0].selection_method == "manual_approved"
    assert len(series) == 1


def test_review_reject(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate()])

    dec = tmp_path / "dec.csv"
    dec.write_text("candidate_id,decision,reviewer_note\nmc_001,reject,no\n", encoding="utf-8")

    groups, series, _ = build_metric_series(f, dec)
    assert groups[0].status != "selected"


def test_multi_approve_conflict(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [
        make_candidate({"candidate_id": "mc_a", "value_normalized": 100}),
        make_candidate({"candidate_id": "mc_b", "value_normalized": 200}),
    ])

    dec = tmp_path / "dec.csv"
    dec.write_text("candidate_id,decision,reviewer_note\nmc_a,approve,ok\nmc_b,approve,ok\n", encoding="utf-8")

    with pytest.raises(ReviewDecisionError, match="Multiple approved"):
        build_metric_series(f, dec)


def test_unknown_candidate_decision_fails(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [make_candidate()])

    dec = tmp_path / "dec.csv"
    dec.write_text("candidate_id,decision,reviewer_note\nmc_fake,approve,ok\n", encoding="utf-8")

    with pytest.raises(ReviewDecisionError, match="unknown candidate_id"):
        build_metric_series(f, dec)


def test_parse_period():
    assert parse_period("2024Q1") == (2024, "Q1", 1)
    assert parse_period("2024H1") == (2024, "H1", 2)
    assert parse_period("2024A") == (2024, "A", 4)
    assert parse_period("unknown") == (0, "unknown", 0)


def test_period_order(tmp_path):
    f = tmp_path / "c.jsonl"
    _write_candidates(f, [
        make_candidate({"candidate_id": "mc_a", "report_period": "2024Q1"}),
        make_candidate({"candidate_id": "mc_b", "report_period": "2024H1", "metric_id": "revenue"}),
        make_candidate({"candidate_id": "mc_c", "report_period": "2024A", "metric_id": "revenue"}),
    ])
    groups, series, _ = build_metric_series(f)
    assert len(series) == 3
    assert series[0].period_order < series[1].period_order < series[2].period_order
