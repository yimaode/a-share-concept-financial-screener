import json
from pathlib import Path

import pytest

from ds_finance_concept.metric_trends.builder import compute_trends
from ds_finance_concept.metric_trends.errors import MetricTrendsError


def make_series(overrides=None):
    d = {
        "series_id": "ms_001",
        "metric_id": "revenue",
        "metric_name": "营业收入",
        "report_period": "2024Q1",
        "period_year": 2024,
        "period_type": "Q1",
        "period_order": 1,
        "value_normalized": 120.0,
        "value_unit_normalized": "CNY",
        "is_percent": False,
        "source_candidate_id": "mc_001",
        "source_pdf": "2024Q1.pdf",
        "page_number": 5,
    }
    if overrides:
        d.update(overrides)
    return d


def _write_series(path: Path, items: list[dict]) -> None:
    lines = [json.dumps(i, ensure_ascii=False) for i in items]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_empty_series(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text("", encoding="utf-8")
    trends, _ = compute_trends(f)
    assert trends == []


def test_bad_json_fails(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text("not json\n", encoding="utf-8")
    with pytest.raises(MetricTrendsError):
        compute_trends(f)


def test_missing_field_fails(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [{"series_id": "ms_1"}])
    with pytest.raises(MetricTrendsError):
        compute_trends(f)


def test_duplicate_conflict_fails(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"series_id": "ms_a", "value_normalized": 100}),
        make_series({"series_id": "ms_b", "value_normalized": 200}),
    ])
    with pytest.raises(MetricTrendsError, match="Conflicting"):
        compute_trends(f)


def test_duplicate_same_ok(tmp_path):
    f = tmp_path / "s.jsonl"
    s = make_series()
    _write_series(f, [s, s])
    trends, warnings = compute_trends(f)
    assert len(trends) == 1
    assert warnings


def test_unknown_period_fails(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [make_series({"report_period": "unknown"})])
    with pytest.raises(MetricTrendsError, match="Unknown"):
        compute_trends(f)


def test_yoy_q1(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2023Q1", "period_year": 2023, "value_normalized": 100}),
        make_series({"report_period": "2024Q1", "period_year": 2024, "value_normalized": 120}),
    ])
    trends, _ = compute_trends(f)
    assert len(trends) == 2
    t2024 = [t for t in trends if t.report_period == "2024Q1"][0]
    assert t2024.yoy == 0.2
    assert t2024.yoy_status == "computed"


def test_yoy_h1(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2023H1", "period_year": 2023, "period_type": "H1", "period_order": 2, "value_normalized": 200}),
        make_series({"report_period": "2024H1", "period_year": 2024, "period_type": "H1", "period_order": 2, "value_normalized": 250}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024H1"][0]
    assert t.yoy == 0.25


def test_yoy_annual(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2023A", "period_year": 2023, "period_type": "A", "period_order": 4, "value_normalized": 1000}),
        make_series({"report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4, "value_normalized": 1100}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024A"][0]
    assert t.yoy == 0.1


def test_yoy_missing_base(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2024Q1", "period_year": 2024, "value_normalized": 100}),
    ])
    trends, _ = compute_trends(f)
    assert trends[0].yoy is None
    assert trends[0].yoy_status == "missing_base"


def test_yoy_previous_zero(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2023Q1", "period_year": 2023, "value_normalized": 0.0}),
        make_series({"report_period": "2024Q1", "period_year": 2024, "value_normalized": 100.0}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024Q1"][0]
    assert t.yoy is None
    assert t.yoy_status == "previous_value_zero"


def test_yoy_unit_mismatch(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2023Q1", "period_year": 2023, "value_unit_normalized": "CNY", "value_normalized": 100}),
        make_series({"report_period": "2024Q1", "period_year": 2024, "value_unit_normalized": "USD", "value_normalized": 120}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024Q1"][0]
    assert t.yoy_status == "unit_mismatch"


def test_gross_margin_change_pp(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"metric_id": "gross_margin", "metric_name": "毛利率", "is_percent": True,
                      "report_period": "2023Q1", "period_year": 2023, "value_normalized": 35.0}),
        make_series({"metric_id": "gross_margin", "metric_name": "毛利率", "is_percent": True,
                      "report_period": "2024Q1", "period_year": 2024, "value_normalized": 38.0}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024Q1"][0]
    assert t.change_pp == 3.0
    assert t.yoy is None


def test_non_percent_no_change_pp(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2023Q1", "period_year": 2023, "value_normalized": 100}),
        make_series({"report_period": "2024Q1", "period_year": 2024, "value_normalized": 120}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024Q1"][0]
    assert t.change_pp is None
    assert t.yoy is not None


def test_sequential_change(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2024Q1", "period_year": 2024, "period_type": "Q1", "period_order": 1, "value_normalized": 100}),
        make_series({"report_period": "2024H1", "period_year": 2024, "period_type": "H1", "period_order": 2, "value_normalized": 300}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024H1"][0]
    assert t.sequential_change == 2.0


def test_sequential_prev_zero(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2024Q1", "period_year": 2024, "value_normalized": 0.0}),
        make_series({"report_period": "2024H1", "period_year": 2024, "period_type": "H1", "period_order": 2, "value_normalized": 100}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024H1"][0]
    assert t.sequential_change is None
    assert t.sequential_status == "previous_value_zero"


def test_cagr_3y(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2021A", "period_year": 2021, "period_type": "A", "period_order": 4, "value_normalized": 100}),
        make_series({"report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4, "value_normalized": 133.1}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024A"][0]
    assert t.cagr_3y is not None
    assert abs(t.cagr_3y - 0.1) < 0.001


def test_cagr_not_annual(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2024Q1", "period_year": 2024, "value_normalized": 100}),
    ])
    trends, _ = compute_trends(f)
    assert trends[0].cagr_3y_status == "not_applicable"


def test_cagr_insufficient_history(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4, "value_normalized": 100}),
    ])
    trends, _ = compute_trends(f)
    assert trends[0].cagr_3y_status == "insufficient_history"


def test_cagr_non_positive(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2021A", "period_year": 2021, "period_type": "A", "period_order": 4, "value_normalized": -50}),
        make_series({"report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4, "value_normalized": 100}),
    ])
    trends, _ = compute_trends(f)
    t = [t for t in trends if t.report_period == "2024A"][0]
    assert t.cagr_3y_status == "non_positive_value"


def test_consecutive_growth(tmp_path):
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2024Q1", "period_year": 2024, "period_type": "Q1", "period_order": 1, "value_normalized": 100}),
        make_series({"report_period": "2024H1", "period_year": 2024, "period_type": "H1", "period_order": 2, "value_normalized": 150}),
        make_series({"report_period": "2024Q3", "period_year": 2024, "period_type": "Q3", "period_order": 3, "value_normalized": 120}),
        make_series({"report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4, "value_normalized": 200}),
    ])
    trends, _ = compute_trends(f)
    counts = {t.report_period: t.consecutive_growth_count for t in trends}
    assert counts["2024H1"] == 1
    assert counts["2024Q3"] == 0
    assert counts["2024A"] == 1


def test_wide_csv_has_metric_columns(tmp_path):
    from ds_finance_concept.metric_trends.writer import write_trends_wide_csv
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2024Q1", "period_year": 2024, "value_normalized": 100}),
        make_series({"report_period": "2024H1", "period_year": 2024, "period_type": "H1", "period_order": 2, "value_normalized": 200}),
    ])
    trends, _ = compute_trends(f)
    out = tmp_path / "wide.csv"
    write_trends_wide_csv(trends, out)
    content = out.read_text(encoding="utf-8")
    assert "revenue__yoy" in content
    assert "revenue__seq" in content


def test_summary_latest_period(tmp_path):
    from ds_finance_concept.metric_trends.writer import write_trend_summary
    f = tmp_path / "s.jsonl"
    _write_series(f, [
        make_series({"report_period": "2023A", "period_year": 2023, "period_type": "A", "period_order": 4, "value_normalized": 100}),
        make_series({"report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4, "value_normalized": 200}),
    ])
    trends, warnings = compute_trends(f)
    out = tmp_path / "summary.json"
    write_trend_summary(trends, warnings, out)
    s = json.loads(out.read_text(encoding="utf-8"))
    assert s["metrics"]["revenue"]["latest_period"] == "2024A"
    assert s["metrics"]["revenue"]["points"] == 2
