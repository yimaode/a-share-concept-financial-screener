import json
from pathlib import Path

from ds_finance_concept.metric_extractor.extractor import (
    _detect_section_regions,
    _detect_table_unit,
    _parse_table_columns,
    extract_metric_candidates,
)
from ds_finance_concept.metric_series.builder import build_metric_series
from ds_finance_concept.metric_series.quality_report import write_metric_quality_report


def _w(path: Path, data) -> None:
    if isinstance(data, list):
        path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in data) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_revenue_not_match_other_income(tmp_path):
    cf = tmp_path / "c.json"
    _w(cf, {"version": "0.1.0", "status": "frozen", "concepts": []})
    pf = tmp_path / "p.jsonl"
    _w(pf, [{"pdf_id": "p1", "source_pdf": "2024Q1.pdf", "relative_path": "2024Q1.pdf",
             "page_number": 1, "text": "其他收益 123 万元", "char_count": 10}])
    mf = tmp_path / "m.jsonl"
    _w(mf, [{"pdf_id": "p1", "page_count": 1}])
    cands, _, _ = extract_metric_candidates(pf, mf, cf)
    rev = [c for c in cands if c.metric_id == "revenue"]
    assert len(rev) == 0


def test_revenue_not_match_investment_income(tmp_path):
    cf = tmp_path / "c.json"
    _w(cf, {"version": "0.1.0", "status": "frozen", "concepts": []})
    pf = tmp_path / "p.jsonl"
    _w(pf, [{"pdf_id": "p1", "source_pdf": "2024Q1.pdf", "relative_path": "2024Q1.pdf",
             "page_number": 1, "text": "投资收益 500 万元", "char_count": 10}])
    mf = tmp_path / "m.jsonl"
    _w(mf, [{"pdf_id": "p1", "page_count": 1}])
    cands, _, _ = extract_metric_candidates(pf, mf, cf)
    rev = [c for c in cands if c.metric_id == "revenue"]
    assert len(rev) == 0


def test_revenue_match_operating_revenue(tmp_path):
    cf = tmp_path / "c.json"
    _w(cf, {"version": "0.1.0", "status": "frozen", "concepts": []})
    pf = tmp_path / "p.jsonl"
    _w(pf, [{"pdf_id": "p1", "source_pdf": "2024Q1.pdf", "relative_path": "2024Q1.pdf",
             "page_number": 1, "text": "营业收入 123 万元", "char_count": 10}])
    mf = tmp_path / "m.jsonl"
    _w(mf, [{"pdf_id": "p1", "page_count": 1}])
    cands, _, _ = extract_metric_candidates(pf, mf, cf)
    rev = [c for c in cands if c.metric_id == "revenue"]
    assert len(rev) >= 1
    assert rev[0].value == 123.0


def test_table_section_detection():
    text = "合并资产负债表\n单位：万元\n项目\n存货 100\n固定资产 200"
    regions = _detect_section_regions(text)
    assert len(regions) >= 1
    assert any(r["section_type"] == "balance_sheet" for r in regions)


def test_table_unit_detection():
    text = "单位：万元\n合并资产负债表\n项目\n存货 100"
    unit = _detect_table_unit(text, 1)
    assert unit == "万元"


def test_table_row_extraction(tmp_path):
    cf = tmp_path / "c.json"
    _w(cf, {"version": "0.1.0", "status": "frozen", "concepts": []})
    pf = tmp_path / "p.jsonl"
    _w(pf, [{"pdf_id": "p1", "source_pdf": "2024Q1.pdf", "relative_path": "2024Q1.pdf",
             "page_number": 1,
             "text": "合并利润表\n单位：万元\n项目\n营业收入 123 100\n归属于上市公司股东的净利润 50",
             "char_count": 50}])
    mf = tmp_path / "m.jsonl"
    _w(mf, [{"pdf_id": "p1", "page_count": 1}])
    cands, _, _ = extract_metric_candidates(pf, mf, cf)
    rev = [c for c in cands if c.metric_id == "revenue"]
    assert len(rev) >= 1


def test_annual_summary_table_maps_each_year_to_its_own_period(tmp_path):
    cf = tmp_path / "c.json"
    _w(cf, {"version": "0.1.0", "status": "frozen", "concepts": []})
    pf = tmp_path / "p.jsonl"
    _w(pf, [])
    mf = tmp_path / "m.jsonl"
    _w(mf, [])
    tf = tmp_path / "tables.jsonl"
    _w(tf, [{
        "pdf_id": "p1", "source_pdf": "2024年年度报告.pdf",
        "relative_path": "2024年年度报告.pdf", "page_number": 8,
        "report_period": "2024A", "section_type": "key_financial_data",
        "unit_raw": "元", "unit_source": "page_text",
        "rows": [
            ["", "2024年", "2023年", "本年比上年\\n增减(%)", "2022年"],
            ["营业收入", "2,415,925,226.35", "2,542,791,117.61", "-4.99", "2,959,962,383.90"],
        ],
    }])

    candidates, _, _ = extract_metric_candidates(pf, mf, cf, tf)
    revenue = [c for c in candidates if c.metric_id == "revenue"]

    assert sorted((c.report_period, c.value_normalized, c.column_role) for c in revenue) == [
        ("2022A", 2959962383.90, "current_period"),
        ("2023A", 2542791117.61, "current_period"),
        ("2024A", 2415925226.35, "current_period"),
    ]
    assert all(c.needs_review is False for c in revenue)


def test_structured_tables_do_not_mix_in_fuzzy_page_candidates(tmp_path):
    cf = tmp_path / "c.json"
    _w(cf, {"version": "0.1.0", "status": "frozen", "concepts": []})
    pf = tmp_path / "p.jsonl"
    _w(pf, [{"pdf_id": "p1", "source_pdf": "2024年年度报告.pdf", "relative_path": "r.pdf",
             "page_number": 1, "text": "营业收入 1 2 3 4", "char_count": 12}])
    mf = tmp_path / "m.jsonl"
    _w(mf, [])
    tf = tmp_path / "tables.jsonl"
    _w(tf, [{"pdf_id": "p1", "source_pdf": "2024年年度报告.pdf", "relative_path": "r.pdf",
             "page_number": 1, "report_period": "2024A", "section_type": "key_financial_data",
             "unit_raw": "元", "unit_source": "page_text",
             "rows": [["", "2024年"], ["营业收入", "1000000"]]}])

    candidates, _, _ = extract_metric_candidates(pf, mf, cf, tf)
    assert len(candidates) == 1
    assert candidates[0].value_normalized == 1000000


def test_annual_summary_headers_classify_years_and_change_column():
    rows = [
        ["", "2024年", "2023年", "本年比上年\\n增减(%)", "2022年"],
        ["营业收入", "1", "2", "3", "4"],
    ]
    columns = _parse_table_columns(rows, "2024A")
    assert [(c["role"], c["report_period"]) for c in columns] == [
        ("header", "2024A"),
        ("current_period", "2024A"),
        ("current_period", "2023A"),
        ("change_column", "2024A"),
        ("current_period", "2022A"),
    ]


def test_quarterly_table_headers_keep_the_quarter_period():
    rows = [
        ["", "2026年第一季度", "2025年第一季度"],
        ["营业收入", "100", "90"],
    ]
    columns = _parse_table_columns(rows, "2026Q1")
    assert [(c["role"], c["report_period"]) for c in columns] == [
        ("header", "2026Q1"),
        ("current_period", "2026Q1"),
        ("current_period", "2025Q1"),
    ]


def test_fixed_assets_zero_not_selected(tmp_path):
    cf = tmp_path / "c.jsonl"
    _w(cf, [{"candidate_id": "mc_1", "metric_id": "fixed_assets", "metric_name": "固定资产",
             "report_period": "2024A", "value_normalized": 0.0, "value_unit_normalized": "CNY",
             "is_percent": False, "confidence": "high", "needs_review": False,
             "source_pdf": "r.pdf", "page_number": 1, "source_snippet": "固定资产",
             "raw_value": "123", "value": 0.0}])
    groups, series, _ = build_metric_series(cf)
    assert len(series) == 0


def test_revenue_not_match_deferred_income(tmp_path):
    cf = tmp_path / "c.json"
    _w(cf, {"version": "0.1.0", "status": "frozen", "concepts": []})
    pf = tmp_path / "p.jsonl"
    _w(pf, [{"pdf_id": "p1", "source_pdf": "2024Q1.pdf", "relative_path": "2024Q1.pdf",
             "page_number": 1, "text": "递延收益 200 万元", "char_count": 10}])
    mf = tmp_path / "m.jsonl"
    _w(mf, [{"pdf_id": "p1", "page_count": 1}])
    cands, _, _ = extract_metric_candidates(pf, mf, cf)
    rev = [c for c in cands if c.metric_id == "revenue"]
    assert len(rev) == 0


def test_quality_report_generates(tmp_path):
    cands = [{"candidate_id": "mc_1", "metric_id": "revenue", "needs_review": False,
              "value_unit_normalized": "CNY", "report_period": "2024A"}]
    groups = [{"metric_id": "revenue", "report_period": "2024A", "status": "selected",
               "value_normalized": 100, "value_unit_normalized": "CNY"}]
    series = [{"metric_id": "revenue", "report_period": "2024A"}]
    out = tmp_path / "report.md"
    write_metric_quality_report(cands, groups, series, str(out))
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "指标质量诊断报告" in content
