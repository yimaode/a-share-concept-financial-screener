import pytest

from ds_finance_concept.concept_builder.concept_candidate_builder import (
    build_concept_candidates,
)
from ds_finance_concept.concept_builder.errors import InsightValidationError


def make_insight(overrides=None):
    defaults = {
        "insight_id": "insight_001",
        "quote_id": "quote_001",
        "investment_claim": "公司成长性良好",
        "candidate_concepts": ["超级成长股"],
        "observable_signals": ["营业收入增长"],
        "possible_financial_metrics": ["revenue_yoy"],
        "possible_report_keywords": ["收入增长", "收入"],
        "not_quantifiable_parts": [],
        "confidence": "high",
    }
    if overrides:
        defaults.update(overrides)
    return defaults


def test_single_insight_candidate():
    insights = [make_insight()]
    candidates = build_concept_candidates(insights)
    assert len(candidates) == 1
    cc = candidates[0]
    assert cc.candidate_concept_id == "super_growth_stock"
    assert cc.canonical_name == "超级成长股"
    assert cc.evidence_count == 1
    assert "quote_001" in cc.source_quote_ids
    assert "insight_001" in cc.source_insight_ids
    assert "营业收入增长" in cc.common_observable_signals


def test_multiple_insights_same_concept():
    insights = [
        make_insight({
            "insight_id": "insight_001",
            "quote_id": "quote_001",
            "candidate_concepts": ["超级成长股"],
        }),
        make_insight({
            "insight_id": "insight_002",
            "quote_id": "quote_002",
            "candidate_concepts": ["超级成长股"],
        }),
    ]
    candidates = build_concept_candidates(insights)
    assert len(candidates) == 1
    cc = candidates[0]
    assert cc.evidence_count == 2
    assert cc.source_quote_ids == sorted(["quote_001", "quote_002"])
    assert cc.source_insight_ids == sorted(["insight_001", "insight_002"])


def test_different_concepts():
    insights = [
        make_insight({
            "insight_id": "i1",
            "quote_id": "q1",
            "candidate_concepts": ["超级成长股"],
        }),
        make_insight({
            "insight_id": "i2",
            "quote_id": "q2",
            "candidate_concepts": ["行业景气"],
        }),
    ]
    candidates = build_concept_candidates(insights)
    assert len(candidates) == 2
    ids = {c.candidate_concept_id for c in candidates}
    assert ids == {"super_growth_stock", "industry_prosperity"}


def test_synonym_concepts_same_id():
    insights = [
        make_insight({
            "insight_id": "i1",
            "quote_id": "q1",
            "candidate_concepts": ["超级成长股"],
        }),
        make_insight({
            "insight_id": "i2",
            "quote_id": "q2",
            "candidate_concepts": ["成长股"],
        }),
        make_insight({
            "insight_id": "i3",
            "quote_id": "q3",
            "candidate_concepts": ["高成长"],
        }),
    ]
    candidates = build_concept_candidates(insights)
    assert len(candidates) == 1
    cc = candidates[0]
    assert cc.candidate_concept_id == "super_growth_stock"
    assert cc.evidence_count == 3


def test_uncategorized_concept():
    insights = [
        make_insight({
            "insight_id": "i1",
            "quote_id": "q1",
            "candidate_concepts": ["未知概念XYZ"],
        }),
    ]
    candidates = build_concept_candidates(insights)
    assert len(candidates) == 1
    cc = candidates[0]
    assert cc.candidate_concept_id == "uncategorized"
    assert cc.needs_manual_review is True
    assert any("未识别概念" in r for r in cc.manual_review_reasons)


def test_empty_insights():
    candidates = build_concept_candidates([])
    assert candidates == []


def test_insight_no_concepts_skipped():
    insights = [
        make_insight({
            "insight_id": "i1",
            "quote_id": "q1",
            "candidate_concepts": [],
        }),
    ]
    candidates = build_concept_candidates(insights)
    assert candidates == []


def test_missing_required_field_raises():
    insights = [{"insight_id": "i1", "quote_id": "q1"}]
    with pytest.raises(InsightValidationError, match="missing required field"):
        build_concept_candidates(insights)


def test_evidence_count_less_than_2_needs_review():
    insights = [make_insight()]
    candidates = build_concept_candidates(insights)
    cc = candidates[0]
    assert cc.evidence_count < 2
    assert cc.needs_manual_review is True
    assert any("证据不足" in r for r in cc.manual_review_reasons)


def test_all_low_confidence_needs_review():
    insights = [
        make_insight({
            "insight_id": "i1",
            "quote_id": "q1",
            "confidence": "low",
            "observable_signals": [],
            "possible_financial_metrics": [],
        }),
        make_insight({
            "insight_id": "i2",
            "quote_id": "q2",
            "confidence": "low",
            "observable_signals": [],
            "possible_financial_metrics": [],
        }),
    ]
    candidates = build_concept_candidates(insights)
    cc = candidates[0]
    assert cc.needs_manual_review is True
    assert any("低置信度" in r for r in cc.manual_review_reasons)


def test_confidence_summary():
    insights = [
        make_insight({
            "insight_id": "i1",
            "quote_id": "q1",
            "confidence": "high",
        }),
        make_insight({
            "insight_id": "i2",
            "quote_id": "q2",
            "confidence": "medium",
        }),
        make_insight({
            "insight_id": "i3",
            "quote_id": "q3",
            "confidence": "low",
        }),
    ]
    candidates = build_concept_candidates(insights)
    cc = candidates[0]
    assert cc.confidence_summary == {"high": 1, "medium": 1, "low": 1}


def test_freq_sort_signals():
    insights = [
        make_insight({
            "insight_id": "i1",
            "quote_id": "q1",
            "observable_signals": ["A", "B"],
        }),
        make_insight({
            "insight_id": "i2",
            "quote_id": "q2",
            "observable_signals": ["B", "C"],
        }),
        make_insight({
            "insight_id": "i3",
            "quote_id": "q3",
            "observable_signals": ["B"],
        }),
    ]
    candidates = build_concept_candidates(insights)
    cc = candidates[0]
    assert cc.common_observable_signals[0] == "B"


def test_insight_with_multiple_concepts():
    insights = [
        make_insight({
            "insight_id": "i1",
            "quote_id": "q1",
            "candidate_concepts": ["超级成长股", "行业景气"],
        }),
    ]
    candidates = build_concept_candidates(insights)
    assert len(candidates) == 2
    ids = {c.candidate_concept_id for c in candidates}
    assert ids == {"super_growth_stock", "industry_prosperity"}


def test_dedup_quote_and_insight_ids():
    insights = [
        make_insight({"insight_id": "i1", "quote_id": "q1", "candidate_concepts": ["超级成长股"]}),
        make_insight({"insight_id": "i1", "quote_id": "q1", "candidate_concepts": ["超级成长股"]}),
    ]
    candidates = build_concept_candidates(insights)
    cc = candidates[0]
    assert cc.source_insight_ids == ["i1"]
    assert cc.source_quote_ids == ["q1"]
    assert cc.evidence_count == 1
