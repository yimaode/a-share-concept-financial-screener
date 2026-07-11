import json
from pathlib import Path

import pytest

from ds_finance_concept.concept_scores.scorer import score_concepts
from ds_finance_concept.concept_scores.errors import ConceptScoreError
from ds_finance_concept.concept_scores.schema import score_to_level


def _w(path: Path, data) -> None:
    if isinstance(data, list):
        lines = [json.dumps(d, ensure_ascii=False) for d in data]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_non_frozen_fails(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {"version": "0.1.0", "status": "draft", "concepts": []})
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [])
    with pytest.raises(ConceptScoreError, match="frozen"):
        score_concepts(c, t, e)


def test_empty_trends_and_evidence(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "super_growth_stock", "name": "超级成长股", "hard_metrics": ["revenue"], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [])

    data, details, _ = score_concepts(c, t, e)
    assert data["concepts"][0]["score"] == 50
    assert data["concepts"][0]["level"] == "weak"


def test_super_growth_high_yoy(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "super_growth_stock", "name": "超级成长股", "hard_metrics": ["revenue"], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [
        {"trend_id": "mt_1", "metric_id": "revenue", "metric_name": "营业收入",
         "report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4,
         "value_normalized": 135, "value_unit_normalized": "CNY", "is_percent": False,
         "yoy": 0.35, "yoy_status": "computed", "consecutive_growth_count": 2,
         "source_candidate_id": "mc_1", "source_pdf": "r.pdf", "page_number": 1}
    ])
    e = tmp_path / "e.jsonl"
    _w(e, [])

    data, details, _ = score_concepts(c, t, e)
    assert data["concepts"][0]["score"] == 70


def test_super_growth_with_evidence(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "super_growth_stock", "name": "超级成长股", "hard_metrics": ["revenue"], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [
        {"evidence_id": "ev_1", "concept_id": "super_growth_stock", "polarity": "positive", "keyword": "成长", "sentence": "test", "negation_detected": False},
        {"evidence_id": "ev_2", "concept_id": "super_growth_stock", "polarity": "negative", "keyword": "下滑", "sentence": "test", "negation_detected": False},
    ])

    data, details, _ = score_concepts(c, t, e)
    assert data["concepts"][0]["positive_hits"] == 1
    assert data["concepts"][0]["negative_hits"] == 1


def test_risk_high_score_means_risk(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "risk_negative_evidence", "name": "风险", "hard_metrics": ["revenue"], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [
        {"trend_id": "mt_1", "metric_id": "revenue", "metric_name": "营业收入",
         "report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4,
         "value_normalized": 80, "value_unit_normalized": "CNY", "is_percent": False,
         "yoy": -0.25, "yoy_status": "computed", "consecutive_growth_count": 0,
         "source_candidate_id": "mc_1", "source_pdf": "r.pdf", "page_number": 1}
    ])
    e = tmp_path / "e.jsonl"
    _w(e, [
        {"evidence_id": "ev_n", "concept_id": "risk_negative_evidence", "polarity": "negative", "keyword": "下滑", "sentence": "test", "negation_detected": False},
    ])

    data, details, _ = score_concepts(c, t, e)
    assert data["concepts"][0]["score"] > 0


def test_generic_scoring(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "unknown_concept", "name": "未知", "hard_metrics": ["revenue"], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [])

    data, details, warnings = score_concepts(c, t, e)
    assert any("Generic scoring" in w for w in warnings)


def test_score_bounds(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "super_growth_stock", "name": "超级成长股", "hard_metrics": [], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [])

    data, details, _ = score_concepts(c, t, e)
    assert 0 <= data["concepts"][0]["score"] <= 100


def test_score_to_level():
    assert score_to_level(-1) == "unknown"
    assert score_to_level(85) == "strong"
    assert score_to_level(65) == "medium"
    assert score_to_level(45) == "weak"
    assert score_to_level(10) == "very_weak"


def test_too_many_positive_hits_score(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "industry_boom", "name": "行业景气", "hard_metrics": [], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [
        {"evidence_id": f"ev_{i}", "concept_id": "industry_boom", "polarity": "positive",
         "keyword": "景气", "sentence": "test", "negation_detected": False}
        for i in range(20)
    ])

    data, details, _ = score_concepts(c, t, e)
    assert 0 <= data["concepts"][0]["score"] <= 100


def test_repeated_same_keyword_counts_as_one_scoring_signal(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {"version": "0.1.0", "status": "frozen", "concepts": [
        {"concept_id": "super_growth_stock", "name": "超级成长股", "hard_metrics": [], "scoring": {}},
    ]})
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [
        {"evidence_id": f"ev_{i}", "concept_id": "super_growth_stock", "polarity": "positive",
         "keyword_group": "growth", "keyword": "成长", "sentence": f"证据{i}"}
        for i in range(10)
    ])
    data, _, _ = score_concepts(c, t, e)
    result = data["concepts"][0]
    assert result["positive_hits"] == 10
    assert result["positive_signals"] == 1
    assert result["score"] == 52


def test_evidence_score_detail_links_to_pdf_page(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {"version": "0.1.0", "status": "frozen", "concepts": [
        {"concept_id": "super_growth_stock", "name": "超级成长股", "hard_metrics": [], "scoring": {}},
    ]})
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [{"evidence_id": "ev_1", "concept_id": "super_growth_stock", "polarity": "positive",
            "keyword_group": "growth", "keyword": "成长", "sentence": "持续成长",
            "source_pdf": "2024年报.pdf", "relative_path": "2024年报.pdf", "page_number": 12}])
    _, details, _ = score_concepts(c, t, e)
    detail = next(d for d in details if d["component"] == "positive_evidence")
    assert detail["evidence_id"] == "ev_1"
    assert "2024年报.pdf p.12" in detail["source_id"]


def test_duplicate_evidence_id_same_ok(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {"version": "0.1.0", "status": "frozen", "concepts": []})
    t = tmp_path / "t.jsonl"
    _w(t, [])
    ev = {"evidence_id": "ev_1", "concept_id": "sg", "polarity": "positive", "keyword": "x", "sentence": "t", "negation_detected": False}
    e = tmp_path / "e.jsonl"
    _w(e, [ev, ev])
    _, _, warnings = score_concepts(c, t, e)
    assert any("Duplicate" in w for w in warnings)


def test_duplicate_evidence_id_diff_fails(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {"version": "0.1.0", "status": "frozen", "concepts": []})
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [
        {"evidence_id": "ev_1", "concept_id": "a", "polarity": "positive", "keyword": "x", "sentence": "t", "negation_detected": False},
        {"evidence_id": "ev_1", "concept_id": "b", "polarity": "positive", "keyword": "x", "sentence": "t", "negation_detected": False},
    ])
    with pytest.raises(ConceptScoreError, match="Duplicate"):
        score_concepts(c, t, e)


def test_supply_shortage_scoring(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "supply_shortage", "name": "供不应求", "hard_metrics": ["contract_liabilities"], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [
        {"trend_id": "mt_1", "metric_id": "contract_liabilities", "metric_name": "合同负债",
         "report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4,
         "value_normalized": 150, "value_unit_normalized": "CNY", "is_percent": False,
         "yoy": 0.4, "yoy_status": "computed", "consecutive_growth_count": 1,
         "source_candidate_id": "mc_1", "source_pdf": "r.pdf", "page_number": 1}
    ])
    e = tmp_path / "e.jsonl"
    _w(e, [])

    data, details, _ = score_concepts(c, t, e)
    assert data["concepts"][0]["score"] == 70


def test_pre_explosion_scoring(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "pre_explosion_stage", "name": "爆发前期", "hard_metrics": [], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [])
    e = tmp_path / "e.jsonl"
    _w(e, [])

    data, details, _ = score_concepts(c, t, e)
    assert data["concepts"][0]["score"] <= 60


def test_core_alpha_scoring(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "core_alpha_company", "name": "核心α公司", "hard_metrics": ["gross_margin"], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [
        {"trend_id": "mt_1", "metric_id": "gross_margin", "metric_name": "毛利率",
         "report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4,
         "value_normalized": 38, "value_unit_normalized": "CNY", "is_percent": True,
         "yoy": None, "change_pp": 3.0, "yoy_status": "computed",
         "consecutive_growth_count": 1, "source_candidate_id": "mc_1", "source_pdf": "r.pdf", "page_number": 1}
    ])
    e = tmp_path / "e.jsonl"
    _w(e, [])

    data, details, _ = score_concepts(c, t, e)
    assert data["concepts"][0]["score"] >= 60


def test_metric_coverage(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [
            {"concept_id": "super_growth_stock", "name": "超级成长股",
             "hard_metrics": ["revenue", "net_profit_attributable", "deducted_net_profit"], "scoring": {}}
        ]
    })
    t = tmp_path / "t.jsonl"
    _w(t, [
        {"trend_id": "mt_1", "metric_id": "revenue", "metric_name": "营业收入",
         "report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4,
         "value_normalized": 135, "value_unit_normalized": "CNY", "is_percent": False,
         "yoy": 0.35, "yoy_status": "computed", "consecutive_growth_count": 2,
         "source_candidate_id": "mc_1", "source_pdf": "r.pdf", "page_number": 1}
    ])
    e = tmp_path / "e.jsonl"
    _w(e, [])

    data, _, _ = score_concepts(c, t, e)
    mc = data["concepts"][0]["metric_coverage"]
    assert mc["required"] == 3
    assert mc["available"] == 1
    assert "net_profit_attributable" in mc["missing"]
    assert "deducted_net_profit" in mc["missing"]


def test_quality_status_requires_usable_yoy_and_marks_unsupported_metric(tmp_path):
    c = tmp_path / "concepts.json"
    _w(c, {
        "version": "0.1.0", "status": "frozen",
        "concepts": [{
            "concept_id": "super_growth_stock", "name": "超级成长股",
            "hard_metrics": ["revenue_yoy", "market_share"],
            "evidence_rules": {"min_evidence_count": 1}, "scoring": {},
        }],
    })
    # 只有单年收入，不能算同比，不能被误报为可用的 revenue_yoy。
    t = tmp_path / "t.jsonl"
    _w(t, [{
        "trend_id": "mt_1", "metric_id": "revenue", "metric_name": "营业收入",
        "report_period": "2024A", "period_year": 2024, "period_type": "A", "period_order": 4,
        "value_normalized": 100, "value_unit_normalized": "CNY", "is_percent": False,
        "yoy": None, "yoy_status": "missing_base", "consecutive_growth_count": 0,
        "source_candidate_id": "akshare", "source_pdf": "akshare", "page_number": 0,
    }])
    e = tmp_path / "e.jsonl"
    _w(e, [])

    data, _, _ = score_concepts(c, t, e)
    result = data["concepts"][0]
    assert result["status"] == "data_incomplete"
    assert result["metric_coverage"]["available"] == 0
    assert result["metric_coverage"]["missing"] == ["revenue_yoy"]
    assert result["metric_coverage"]["unsupported"] == ["market_share"]
