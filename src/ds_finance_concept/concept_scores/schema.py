import hashlib
from dataclasses import dataclass, field

SCORE_CSV_FIELDS = [
    "concept_id", "concept_name", "score", "level", "status",
    "positive_hits", "negative_hits", "available_metrics", "missing_metrics", "warnings",
]

DETAIL_CSV_FIELDS = [
    "detail_id", "concept_id", "component", "source_type",
    "source_id", "metric_id", "evidence_id",
    "points", "reason", "raw_value", "report_period",
]


def score_to_level(score: int) -> str:
    if score < 0:
        return "unknown"
    if score >= 80:
        return "strong"
    if score >= 60:
        return "medium"
    if score >= 40:
        return "weak"
    return "very_weak"


def generate_detail_id(concept_id: str, component: str, reason: str) -> str:
    key = f"{concept_id}|{component}|{reason}"
    sha = hashlib.sha256(key.encode()).hexdigest()[:12]
    return f"sd_{sha}"
