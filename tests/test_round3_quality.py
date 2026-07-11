import json
from pathlib import Path

from ds_finance_concept.metric_series.builder import build_metric_series, _is_auto_selectable
from ds_finance_concept.metric_extractor.extractor import _detect_column_roles, _detect_section_regions


def _w(path, data):
    if isinstance(data, list):
        path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in data) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_small_amount_revenue_blocked(tmp_path):
    cf = tmp_path / "c.jsonl"
    _w(cf, [{"candidate_id": "mc_1", "metric_id": "revenue", "metric_name": "营业收入",
             "report_period": "2024A", "value_normalized": 431.1, "value_unit_normalized": "CNY",
             "is_percent": False, "confidence": "high", "needs_review": False,
             "source_pdf": "r.pdf", "page_number": 1, "source_snippet": "营业收入 431.1",
             "raw_value": "431.1", "value": 431.1}])
    groups, series, _ = build_metric_series(cf)
    assert len(series) == 0


def test_small_amount_block_reason(tmp_path):
    cf = tmp_path / "c.jsonl"
    _w(cf, [{"candidate_id": "mc_1", "metric_id": "revenue", "metric_name": "营业收入",
             "report_period": "2024A", "value_normalized": 97.6, "value_unit_normalized": "CNY",
             "is_percent": False, "confidence": "high", "needs_review": False,
             "source_pdf": "r.pdf", "page_number": 1, "source_snippet": "营业收入 97.6",
             "raw_value": "97.6", "value": 97.6}])
    groups, _, _ = build_metric_series(cf)
    rq = [g for g in groups if g.status != "selected"]
    assert len(rq) >= 1
    assert any("implausibly_small" in " ".join(rq[0].review_reasons) for _ in [1])


def test_column_role_current_period():
    roles = _detect_column_roles("合并利润表\n项目 本期金额 上期金额\n", 0, 10)
    assert any(r["role"] == "current_period" for r in roles)
    assert any(r["role"] == "previous_period" for r in roles)


def test_column_role_previous_period():
    roles = _detect_column_roles("主要会计数据\n项目 本期 上期\n", 0, 10)
    roles_list = [(r["label"], r["role"]) for r in roles]
    assert ("本期", "current_period") in roles_list


def test_section_type_income_statement():
    regions = _detect_section_regions("合并及母公司利润表\n项目 本期金额\n")
    assert any(r["section_type"] == "income_statement" for r in regions)


def test_section_type_balance_sheet():
    regions = _detect_section_regions("合并及母公司资产负债表\n项目 期末余额\n")
    assert any(r["section_type"] == "balance_sheet" for r in regions)


def test_section_type_cashflow():
    regions = _detect_section_regions("合并及母公司现金流量表\n项目 本期金额\n")
    assert any(r["section_type"] == "cashflow_statement" for r in regions)


def test_amount_metric_not_from_wrong_section():
    c = {
        "confidence": "high", "needs_review": False,
        "report_period": "2024A", "value_unit_normalized": "CNY",
        "value_normalized": 5000000000.0, "metric_id": "revenue",
        "is_percent": False, "section_type": "balance_sheet",
    }
    assert _is_auto_selectable(c) is False


def test_inventory_not_from_income_statement():
    c = {
        "confidence": "high", "needs_review": False,
        "report_period": "2024A", "value_unit_normalized": "CNY",
        "value_normalized": 5000000000.0, "metric_id": "inventory",
        "is_percent": False, "section_type": "income_statement",
    }
    assert _is_auto_selectable(c) is False


def test_ocf_not_from_income_statement():
    c = {
        "confidence": "high", "needs_review": False,
        "report_period": "2024A", "value_unit_normalized": "CNY",
        "value_normalized": 5000000000.0, "metric_id": "operating_cashflow",
        "is_percent": False, "section_type": "income_statement",
    }
    assert _is_auto_selectable(c) is False


def test_column_role_non_current_blocked():
    cf = Path("/tmp/test_col.jsonl")
    _w(cf, [{"candidate_id": "mc_1", "metric_id": "revenue", "metric_name": "营业收入",
             "report_period": "2024A", "value_normalized": 5000000000.0, "value_unit_normalized": "CNY",
             "is_percent": False, "confidence": "high", "needs_review": False,
             "source_pdf": "r.pdf", "page_number": 1, "source_snippet": "test",
             "raw_value": "50亿", "value": 5000000000.0, "column_role": "previous_period"}])
    groups, series, _ = build_metric_series(cf)
    assert len(series) == 0
    Path("/tmp/test_col.jsonl").unlink(missing_ok=True)
