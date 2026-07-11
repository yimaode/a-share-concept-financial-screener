import hashlib
from dataclasses import dataclass, field


@dataclass
class MetricCandidate:
    candidate_id: str = ""
    metric_id: str = ""
    metric_name: str = ""
    matched_alias: str = ""
    raw_value: str = ""
    value: float = 0.0
    value_unit_raw: str = ""
    value_normalized: float = 0.0
    value_unit_normalized: str = ""
    is_percent: bool = False
    report_period: str = ""
    source_pdf: str = ""
    relative_path: str = ""
    pdf_id: str = ""
    page_number: int = 0
    source_snippet: str = ""
    confidence: str = ""
    needs_review: bool = False
    review_reasons: list = field(default_factory=list)
    section_type: str = ""
    section_name: str = ""
    column_role: str = ""
    column_label: str = ""
    unit_source: str = ""


def generate_candidate_id(
    metric_id: str,
    raw_value: str,
    pdf_id: str,
    page_number: int,
    source_snippet: str,
) -> str:
    key = f"{metric_id}|{raw_value}|{pdf_id}|{page_number}|{source_snippet}"
    sha = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"mc_{sha}"


CSV_FIELDS = [
    "candidate_id",
    "metric_id",
    "metric_name",
    "matched_alias",
    "raw_value",
    "value",
    "value_unit_raw",
    "value_normalized",
    "value_unit_normalized",
    "is_percent",
    "report_period",
    "source_pdf",
    "relative_path",
    "page_number",
    "confidence",
    "needs_review",
    "review_reasons",
    "source_snippet",
]
