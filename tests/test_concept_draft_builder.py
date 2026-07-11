from ds_finance_concept.concept_builder.concept_draft_builder import build_draft_concepts
from ds_finance_concept.concept_builder.concept_templates import CONCEPT_TEMPLATES


def test_empty_candidates_generates_6_draft_concepts():
    draft = build_draft_concepts([])
    assert len(draft) == 6
    for c in draft:
        assert "concept_id" in c
        assert "name" in c
        assert "definition" in c
        assert c["manual_review"]["required"] is True
        assert c["evidence_count"] == 0


def test_candidates_with_matching_concept_merge_quote_ids():
    candidates = [
        {
            "candidate_concept_id": "super_growth_stock",
            "canonical_name": "超级成长股",
            "source_quote_ids": ["quote_a", "quote_b"],
            "source_insight_ids": ["i1", "i2"],
        },
    ]
    draft = build_draft_concepts(candidates)
    sg = [c for c in draft if c["concept_id"] == "super_growth_stock"][0]
    assert "quote_a" in sg["source_quote_ids"]
    assert "quote_b" in sg["source_quote_ids"]
    assert sg["evidence_count"] == 2


def test_duplicate_quote_ids_dedupped_and_sorted():
    candidates = [
        {
            "candidate_concept_id": "super_growth_stock",
            "canonical_name": "超级成长股",
            "source_quote_ids": ["quote_b", "quote_a"],
            "source_insight_ids": ["i1"],
        },
        {
            "candidate_concept_id": "super_growth_stock",
            "canonical_name": "超级成长股",
            "source_quote_ids": ["quote_a", "quote_c"],
            "source_insight_ids": ["i2"],
        },
    ]
    draft = build_draft_concepts(candidates)
    sg = [c for c in draft if c["concept_id"] == "super_growth_stock"][0]
    assert sg["source_quote_ids"] == ["quote_a", "quote_b", "quote_c"]
    assert sg["evidence_count"] == 3


def test_uncategorized_not_matched_to_any_template():
    candidates = [
        {
            "candidate_concept_id": "uncategorized",
            "canonical_name": "未知概念",
            "source_quote_ids": ["q1"],
            "source_insight_ids": ["i1"],
        },
    ]
    draft = build_draft_concepts(candidates)
    for c in draft:
        assert c["evidence_count"] == 0


def test_industry_prosperity_maps_to_industry_boom():
    candidates = [
        {
            "candidate_concept_id": "industry_prosperity",
            "canonical_name": "行业景气",
            "source_quote_ids": ["q1", "q2"],
            "source_insight_ids": ["i1", "i2"],
        },
    ]
    draft = build_draft_concepts(candidates)
    ib = [c for c in draft if c["concept_id"] == "industry_boom"][0]
    assert ib["evidence_count"] == 2
    assert ib["source_quote_ids"] == ["q1", "q2"]


def test_evidence_below_threshold_needs_review():
    candidates = [
        {
            "candidate_concept_id": "super_growth_stock",
            "canonical_name": "超级成长股",
            "source_quote_ids": ["q1"],
            "source_insight_ids": ["i1"],
        },
    ]
    draft = build_draft_concepts(candidates)
    sg = [c for c in draft if c["concept_id"] == "super_growth_stock"][0]
    assert sg["evidence_count"] == 1
    assert sg["manual_review"]["required"] is True
    assert "证据不足" in sg["manual_review"]["reason"]


def test_evidence_above_threshold_no_review():
    candidates = [
        {
            "candidate_concept_id": "super_growth_stock",
            "canonical_name": "超级成长股",
            "source_quote_ids": ["q1", "q2"],
            "source_insight_ids": ["i1", "i2"],
        },
    ]
    draft = build_draft_concepts(candidates)
    sg = [c for c in draft if c["concept_id"] == "super_growth_stock"][0]
    assert sg["evidence_count"] == 2
    assert sg["manual_review"]["required"] is False
