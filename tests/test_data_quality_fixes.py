import json
from pathlib import Path

from ds_finance_concept.metric_extractor.extractor import (
    _detect_page_unit,
    _detect_report_period,
    _extract_snippet_lines,
)
from ds_finance_concept.metric_series.builder import _is_auto_selectable
from ds_finance_concept.pdf_extractor.extractor import extract_pdf_directory


def test_detect_period_chinese_h1():
    assert _detect_report_period("2018年半年度报告.PDF", "") == "2018H1"
    assert _detect_report_period("2018-08-22_2018年半年度报告.PDF", "") == "2018H1"
    assert _detect_report_period("2019年中期报告.pdf", "") == "2019H1"
    assert _detect_report_period("2020半年度报告.PDF", "") == "2020H1"


def test_detect_period_chinese_q1():
    assert _detect_report_period("2018年第一季度报告.PDF", "") == "2018Q1"
    assert _detect_report_period("2019年一季度报告.pdf", "") == "2019Q1"
    assert _detect_report_period("2020一季报.pdf", "") == "2020Q1"


def test_detect_period_chinese_q3():
    assert _detect_report_period("2018年第三季度报告.PDF", "") == "2018Q3"
    assert _detect_report_period("2019年三季度报告.pdf", "") == "2019Q3"
    assert _detect_report_period("2020三季报.pdf", "") == "2020Q3"


def test_detect_period_chinese_annual():
    assert _detect_report_period("2018年年度报告.PDF", "") == "2018A"
    assert _detect_report_period("2019年度报告.pdf", "") == "2019A"
    assert _detect_report_period("2020年年报.pdf", "") == "2020A"


def test_detect_period_english_formats():
    assert _detect_report_period("2024Q1.pdf", "") == "2024Q1"
    assert _detect_report_period("2024H1.pdf", "") == "2024H1"
    assert _detect_report_period("2024Q3.pdf", "") == "2024Q3"
    assert _detect_report_period("2024A.pdf", "") == "2024A"


def test_detect_period_unknown():
    assert _detect_report_period("unknown_report.pdf", "random text") == "unknown"


def test_detect_page_unit_yuan():
    assert _detect_page_unit("单位：元") == "元"
    assert _detect_page_unit("单位：万元") == "万元"
    assert _detect_page_unit("单位：亿元") == "亿元"


def test_detect_page_unit_rmb():
    assert _detect_page_unit("单位：人民币元") == "元"
    assert _detect_page_unit("单位：人民币万元") == "万元"


def test_detect_page_unit_disclaimer():
    assert _detect_page_unit("除特别注明外，金额单位为人民币万元") == "万元"
    assert _detect_page_unit("除特别注明外,金额单位为人民币元") == "元"


def test_detect_page_unit_conflict():
    assert _detect_page_unit("单位：万元 单位：元") is None


def test_detect_page_unit_none():
    assert _detect_page_unit("普通文本没有单位信息") is None


def test_extract_snippet_lines():
    lines = [
        "公司2024年报告",
        "营业收入 1,234.56 万元",
        "同比增长15%",
        "净利润良好",
        "后续展望",
    ]
    snippet = _extract_snippet_lines(lines, 10, 13, 18, 30)
    assert "营业收入" in " ".join(snippet)


def test_is_auto_selectable_zero_amount(tmp_path):
    c = {
        "confidence": "high", "needs_review": False,
        "report_period": "2024Q1", "value_unit_normalized": "CNY",
        "value_normalized": 0.0, "metric_id": "revenue",
        "is_percent": False, "raw_value": "0 万元",
    }
    assert _is_auto_selectable(c) is False


def test_is_auto_selectable_amount_unit_unknown():
    c = {
        "confidence": "high", "needs_review": False,
        "report_period": "2024Q1", "value_unit_normalized": "unknown",
        "value_normalized": 100.0, "metric_id": "revenue",
        "is_percent": False,
    }
    assert _is_auto_selectable(c) is False


def test_is_auto_selectable_gm_non_percent():
    c = {
        "confidence": "high", "needs_review": False,
        "report_period": "2024Q1", "value_unit_normalized": "CNY",
        "value_normalized": 35.0, "metric_id": "gross_margin",
        "is_percent": False,
    }
    assert _is_auto_selectable(c) is False


def test_pdf_uppercase_extension(tmp_path):
    import fitz
    d = tmp_path / "pdfs"
    d.mkdir()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 100), "Test content")
    doc.save(str(d / "test.PDF"))
    doc.close()

    manifests, pages = extract_pdf_directory(d)
    assert len(manifests) == 1
    assert manifests[0].source_pdf == "test.PDF"
    assert manifests[0].extract_status == "success"


def test_excel_list_field_no_crash(tmp_path):
    from ds_finance_concept.reporting.excel_exporter import export_excel
    for f in ["c.jsonl", "s.jsonl", "t.jsonl", "e.jsonl"]:
        (tmp_path / f).write_text("", encoding="utf-8")

    scores = tmp_path / "scores.json"
    scores.write_text(json.dumps({
        "concepts": [{"concept_id": "sg", "name": "test", "metric_coverage": {"a": 1}, "warnings": ["w1"]}]
    }, ensure_ascii=False), encoding="utf-8")

    out = tmp_path / "out.xlsx"
    export_excel("test", tmp_path / "c.jsonl", tmp_path / "s.jsonl",
                 tmp_path / "t.jsonl", tmp_path / "e.jsonl", scores, out)
    assert out.exists()
