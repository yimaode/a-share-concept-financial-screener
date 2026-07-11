import hashlib
from dataclasses import dataclass

from .errors import InsightValidationError


VALID_CONFIDENCE = frozenset({"low", "medium", "high"})
VALID_EXTRACTION_METHODS = frozenset({"rule_based_v1"})
LIST_FIELDS = frozenset({
    "candidate_concepts",
    "observable_signals",
    "possible_financial_metrics",
    "possible_report_keywords",
    "not_quantifiable_parts",
})


@dataclass(frozen=True)
class InsightCard:
    insight_id: str
    quote_id: str
    source_file: str
    heading_path: list[str]
    original_text: str
    investment_claim: str
    candidate_concepts: list[str]
    observable_signals: list[str]
    possible_financial_metrics: list[str]
    possible_report_keywords: list[str]
    not_quantifiable_parts: list[str]
    confidence: str
    extraction_method: str


def validate_insight_card(card: InsightCard) -> None:
    if not card.insight_id:
        raise InsightValidationError("insight_id must not be empty")
    if card.confidence not in VALID_CONFIDENCE:
        raise InsightValidationError(
            f"Invalid confidence: {card.confidence!r}, must be one of low/medium/high"
        )
    if card.extraction_method not in VALID_EXTRACTION_METHODS:
        raise InsightValidationError(
            f"Invalid extraction_method: {card.extraction_method!r}, must be rule_based_v1"
        )
    for field_name in LIST_FIELDS:
        value = getattr(card, field_name)
        if value is None:
            raise InsightValidationError(f"{field_name} must not be None")


def insight_card_to_dict(card: InsightCard) -> dict:
    from dataclasses import asdict

    return asdict(card)
