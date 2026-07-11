from dataclasses import dataclass, field


@dataclass
class ConceptCandidate:
    candidate_concept_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    source_quote_ids: list[str] = field(default_factory=list)
    source_insight_ids: list[str] = field(default_factory=list)
    summary_definition: str = ""
    common_observable_signals: list[str] = field(default_factory=list)
    common_financial_metrics: list[str] = field(default_factory=list)
    common_report_keywords: list[str] = field(default_factory=list)
    common_not_quantifiable_parts: list[str] = field(default_factory=list)
    confidence_summary: dict[str, int] = field(
        default_factory=lambda: {"high": 0, "medium": 0, "low": 0}
    )
    evidence_count: int = 0
    needs_manual_review: bool = False
    manual_review_reasons: list[str] = field(default_factory=list)


def concept_candidate_to_dict(cc: ConceptCandidate) -> dict:
    return {
        "candidate_concept_id": cc.candidate_concept_id,
        "canonical_name": cc.canonical_name,
        "aliases": cc.aliases,
        "source_quote_ids": cc.source_quote_ids,
        "source_insight_ids": cc.source_insight_ids,
        "summary_definition": cc.summary_definition,
        "common_observable_signals": cc.common_observable_signals,
        "common_financial_metrics": cc.common_financial_metrics,
        "common_report_keywords": cc.common_report_keywords,
        "common_not_quantifiable_parts": cc.common_not_quantifiable_parts,
        "confidence_summary": cc.confidence_summary,
        "evidence_count": cc.evidence_count,
        "needs_manual_review": cc.needs_manual_review,
        "manual_review_reasons": cc.manual_review_reasons,
    }
