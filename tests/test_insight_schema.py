import pytest

from ds_finance_concept.concept_builder.errors import InsightValidationError
from ds_finance_concept.concept_builder.insight_schema import (
    InsightCard,
    insight_card_to_dict,
    validate_insight_card,
)


def make_valid_card(**overrides) -> InsightCard:
    defaults = {
        "insight_id": "insight_abc123456789",
        "quote_id": "quote_abc123456789",
        "source_file": "001.md",
        "heading_path": ["H1"],
        "original_text": "原文",
        "investment_claim": "原文结论",
        "candidate_concepts": [],
        "observable_signals": [],
        "possible_financial_metrics": [],
        "possible_report_keywords": [],
        "not_quantifiable_parts": [],
        "confidence": "low",
        "extraction_method": "rule_based_v1",
    }
    defaults.update(overrides)
    return InsightCard(**defaults)


def test_valid_card_passes_validation():
    card = make_valid_card()
    validate_insight_card(card)


def test_empty_insight_id_raises():
    card = make_valid_card(insight_id="")
    with pytest.raises(InsightValidationError, match="insight_id must not be empty"):
        validate_insight_card(card)


def test_invalid_confidence_raises():
    card = make_valid_card(confidence="extreme")
    with pytest.raises(InsightValidationError, match="Invalid confidence"):
        validate_insight_card(card)


def test_invalid_extraction_method_raises():
    card = make_valid_card(extraction_method="llm_v2")
    with pytest.raises(InsightValidationError, match="Invalid extraction_method"):
        validate_insight_card(card)


def test_list_field_none_raises():
    for field in ("candidate_concepts", "observable_signals", "possible_financial_metrics",
                  "possible_report_keywords", "not_quantifiable_parts"):
        card = make_valid_card(**{field: None})
        with pytest.raises(InsightValidationError, match=f"{field} must not be None"):
            validate_insight_card(card)


def test_insight_card_to_dict():
    card = make_valid_card(
        candidate_concepts=["超级成长股"],
        confidence="high",
    )
    d = insight_card_to_dict(card)
    assert d["insight_id"] == "insight_abc123456789"
    assert d["candidate_concepts"] == ["超级成长股"]
    assert d["confidence"] == "high"
    assert d["extraction_method"] == "rule_based_v1"


def test_insight_card_is_frozen():
    card = make_valid_card()
    with pytest.raises(Exception):
        card.insight_id = "x"
