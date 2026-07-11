import json
from pathlib import Path

import pytest

from ds_finance_concept.metric_extractor.errors import ConceptsNotFrozenError
from ds_finance_concept.metric_extractor.extractor import (
    _build_alias_map,
    _detect_report_period,
    _is_standalone_year,
    _parse_number,
    extract_metric_candidates,
)


def test_parse_number_wan():
    val, norm, unit, is_pct = _parse_number("1,234.56", "万元")
    assert val == 1234.56
    assert norm == 12345600.0
    assert unit == "CNY"
    assert is_pct is False


def test_parse_number_yi():
    val, norm, unit, is_pct = _parse_number("1.2", "亿元")
    assert val == 1.2
    assert norm == 120000000.0
    assert unit == "CNY"


def test_parse_number_percent():
    val, norm, unit, is_pct = _parse_number("12.5", "%")
    assert val == 12.5
    assert is_pct is True
    assert unit == "percent"


def test_parse_number_negative():
    val, norm, unit, is_pct = _parse_number("-123", "万元")
    assert val == -123.0
    assert norm == -1230000.0


def test_parse_number_parenthesis_negative():
    val, norm, unit, is_pct = _parse_number("-2.5", "亿元")
    assert val == -2.5


def test_parse_number_no_unit():
    val, norm, unit, is_pct = _parse_number("500", "")
    assert unit == "unknown"


def test_is_standalone_year():
    assert _is_standalone_year("2024 年报告", 0, 4) is True
    assert _is_standalone_year("营收 2024 万元", 3, 7) is True


def test_detect_report_period_q1():
    result = _detect_report_period("2024Q1.pdf", "2024年第一季度报告")
    assert result == "2024Q1"


def test_detect_report_period_annual():
    result = _detect_report_period("2024年度报告.pdf", "")
    assert result == "2024A"


def test_detect_report_period_unknown():
    result = _detect_report_period("report.pdf", "some random text")
    assert result == "unknown"


def test_build_alias_map():
    concepts = []
    am = _build_alias_map(concepts)
    assert "营业收入" in am
    assert ("revenue", "营业收入", "营业收入") in am["营业收入"]


def test_extract_revenue_candidate(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "2024Q1.pdf",
            "relative_path": "2024Q1.pdf",
            "page_number": 5,
            "text": "报告期内公司实现营业收入 1,234.56 万元，同比增长15%。",
            "char_count": 30,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    candidates, _, _ = extract_metric_candidates(pages_file, manifest_file, concepts_file)
    assert len(candidates) >= 1
    c = candidates[0]
    assert c.metric_id == "revenue"
    assert c.matched_alias == "营业收入"
    assert c.value == 1234.56
    assert c.value_normalized == 12345600.0
    assert c.report_period == "2024Q1"
    assert c.candidate_id.startswith("mc_")


def test_net_profit_candidate(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "2024H1.pdf",
            "relative_path": "2024H1.pdf",
            "page_number": 10,
            "text": "归属于上市公司股东的净利润为 5.6 亿元。",
            "char_count": 20,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    candidates, _, _ = extract_metric_candidates(pages_file, manifest_file, concepts_file)
    assert len(candidates) >= 1
    c = candidates[0]
    assert c.metric_id == "net_profit_attributable"
    assert c.value_normalized == 560000000.0


def test_operating_cashflow_candidate(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "2024Q1.pdf",
            "relative_path": "2024Q1.pdf",
            "page_number": 8,
            "text": "经营活动产生的现金流量净额为 (2.5) 亿元。",
            "char_count": 20,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    candidates, _, _ = extract_metric_candidates(pages_file, manifest_file, concepts_file)
    assert len(candidates) >= 1
    c = candidates[0]
    assert c.metric_id == "operating_cashflow"
    assert c.value == -2.5


def test_gross_margin_percent(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "2024A.pdf",
            "relative_path": "2024A.pdf",
            "page_number": 12,
            "text": "公司综合毛利率为 35.8%。",
            "char_count": 12,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    candidates, _, _ = extract_metric_candidates(pages_file, manifest_file, concepts_file)
    assert len(candidates) >= 1
    c = candidates[0]
    assert c.metric_id == "gross_margin"
    assert c.is_percent is True
    assert c.value == 35.8


def test_no_unit_needs_review(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "2024Q1.pdf",
            "relative_path": "2024Q1.pdf",
            "page_number": 1,
            "text": "营业收入 500",
            "char_count": 8,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    candidates, _, _ = extract_metric_candidates(pages_file, manifest_file, concepts_file)
    assert len(candidates) >= 1
    c = candidates[0]
    assert c.value_unit_normalized == "unknown"
    assert c.needs_review is True


def test_multi_value_needs_review(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "2024Q1.pdf",
            "relative_path": "2024Q1.pdf",
            "page_number": 1,
            "text": "营业收入 100 万元 200 万元",
            "char_count": 16,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    candidates, _, _ = extract_metric_candidates(pages_file, manifest_file, concepts_file)
    for c in candidates:
        assert c.needs_review is True


def test_year_not_financial_value(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "2024Q1.pdf",
            "relative_path": "2024Q1.pdf",
            "page_number": 1,
            "text": "公司 2024 年营业收入 500 万元",
            "char_count": 16,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    candidates, _, _ = extract_metric_candidates(pages_file, manifest_file, concepts_file)
    values = [c.value for c in candidates]
    assert 2024 not in values


def test_report_period_unknown_needs_review(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "unknown_report.pdf",
            "relative_path": "unknown_report.pdf",
            "page_number": 1,
            "text": "营业收入 100 万元",
            "char_count": 10,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    candidates, _, _ = extract_metric_candidates(pages_file, manifest_file, concepts_file)
    assert len(candidates) >= 1
    c = candidates[0]
    assert c.report_period == "unknown"
    assert c.needs_review is True


def test_non_frozen_fails(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "draft",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text("", encoding="utf-8")

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text("", encoding="utf-8")

    with pytest.raises(ConceptsNotFrozenError):
        extract_metric_candidates(pages_file, manifest_file, concepts_file)


def test_empty_pages_no_candidates(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text("", encoding="utf-8")

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text("", encoding="utf-8")

    candidates, _, _ = extract_metric_candidates(pages_file, manifest_file, concepts_file)
    assert candidates == []


def test_bad_json_line_fails(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text("not json\n", encoding="utf-8")

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text("", encoding="utf-8")

    with pytest.raises(Exception):
        extract_metric_candidates(pages_file, manifest_file, concepts_file)
