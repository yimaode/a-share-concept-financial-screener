from ds_finance_concept.concept_builder.concept_candidate_schema import (
    ConceptCandidate,
    concept_candidate_to_dict,
)


def test_concept_candidate_defaults():
    cc = ConceptCandidate(
        candidate_concept_id="test_id",
        canonical_name="测试概念",
    )
    assert cc.candidate_concept_id == "test_id"
    assert cc.canonical_name == "测试概念"
    assert cc.aliases == []
    assert cc.source_quote_ids == []
    assert cc.source_insight_ids == []
    assert cc.summary_definition == ""
    assert cc.evidence_count == 0
    assert cc.needs_manual_review is False
    assert cc.manual_review_reasons == []
    assert cc.confidence_summary == {"high": 0, "medium": 0, "low": 0}


def test_concept_candidate_to_dict():
    cc = ConceptCandidate(
        candidate_concept_id="super_growth_stock",
        canonical_name="超级成长股",
        aliases=[],
        source_quote_ids=["q1", "q2"],
        source_insight_ids=["i1", "i2"],
        summary_definition="",
        common_observable_signals=["营业收入增长"],
        common_financial_metrics=["revenue_yoy"],
        common_report_keywords=["收入"],
        common_not_quantifiable_parts=[],
        confidence_summary={"high": 1, "medium": 1, "low": 0},
        evidence_count=2,
        needs_manual_review=False,
    )
    d = concept_candidate_to_dict(cc)
    assert d["candidate_concept_id"] == "super_growth_stock"
    assert d["evidence_count"] == 2
    assert d["confidence_summary"]["high"] == 1
    assert "revenue_yoy" in d["common_financial_metrics"]
