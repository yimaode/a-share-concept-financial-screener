import json, csv
from pathlib import Path

from ds_finance_concept.metric_extractor.extractor import extract_metric_candidates
from ds_finance_concept.metric_extractor.writer import write_high_confidence_table_csv
from ds_finance_concept.metric_extractor.schema import MetricCandidate
from ds_finance_concept.metric_series.builder import _is_auto_selectable


def _w(path, data):
    if isinstance(data, list):
        path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in data) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_dataclass_has_new_fields():
    c = MetricCandidate(section_type="income_statement", column_role="current_period",
                        column_label="本期", unit_source="table_header")
    assert c.section_type == "income_statement"
    assert c.column_role == "current_period"


def test_hc_csv_filters_non_section(tmp_path):
    cs = [
        MetricCandidate(section_type="", confidence="high"),
        MetricCandidate(section_type="income_statement", confidence="high",
                        value_normalized=100.0, value_unit_normalized="CNY", report_period="2024A"),
    ]
    out = tmp_path / "hc.csv"
    write_high_confidence_table_csv(cs, out)
    with open(out) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1


def test_hc_csv_filters_unknown_unit(tmp_path):
    cs = [
        MetricCandidate(section_type="income_statement", confidence="high",
                        value_unit_normalized="unknown", report_period="2024A"),
    ]
    out = tmp_path / "hc.csv"
    write_high_confidence_table_csv(cs, out)
    with open(out) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 0


def test_hc_csv_filters_unknown_period(tmp_path):
    cs = [
        MetricCandidate(section_type="income_statement", confidence="high",
                        value_normalized=100.0, value_unit_normalized="CNY", report_period="unknown"),
    ]
    out = tmp_path / "hc.csv"
    write_high_confidence_table_csv(cs, out)
    with open(out) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 0


def test_hc_csv_keeps_valid(tmp_path):
    cs = [
        MetricCandidate(section_type="income_statement", confidence="high",
                        value_normalized=100.0, value_unit_normalized="CNY", report_period="2024A"),
    ]
    out = tmp_path / "hc.csv"
    write_high_confidence_table_csv(cs, out)
    with open(out) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1


def test_hc_csv_empty_has_header(tmp_path):
    out = tmp_path / "hc.csv"
    write_high_confidence_table_csv([], out)
    assert "metric_id" in out.read_text(encoding="utf-8")


def test_section_type_stored_in_candidate(tmp_path):
    cf = tmp_path / "c.json"
    _w(cf, {"version": "0.1.0", "status": "frozen", "concepts": []})
    pf = tmp_path / "p.jsonl"
    _w(pf, [{"pdf_id": "p1", "source_pdf": "2024A.pdf", "relative_path": "2024A.pdf",
             "page_number": 1, "text": "合并利润表\n单位：万元\n营业收入 500000 万元", "char_count": 30}])
    mf = tmp_path / "m.jsonl"
    _w(mf, [{"pdf_id": "p1", "page_count": 1}])
    cands, _, _ = extract_metric_candidates(pf, mf, cf)
    table_cands = [c for c in cands if c.section_type]
    assert len(table_cands) > 0
    assert table_cands[0].section_type == "income_statement"


def test_column_role_current_period_selected():
    c = {"confidence": "high", "needs_review": False, "report_period": "2024A",
         "value_unit_normalized": "CNY", "value_normalized": 5000000000.0,
         "metric_id": "revenue", "is_percent": False,
         "column_role": "current_period"}
    assert _is_auto_selectable(c) is True


def test_column_role_previous_period_not_selected():
    c = {"confidence": "high", "needs_review": False, "report_period": "2024A",
         "value_unit_normalized": "CNY", "value_normalized": 5000000000.0,
         "metric_id": "revenue", "is_percent": False,
         "column_role": "previous_period"}
    assert _is_auto_selectable(c) is False


def test_change_column_not_selected():
    c = {"confidence": "high", "needs_review": False, "report_period": "2024A",
         "value_unit_normalized": "CNY", "value_normalized": 5000000000.0,
         "metric_id": "revenue", "is_percent": False,
         "column_role": "change_column"}
    assert _is_auto_selectable(c) is False
