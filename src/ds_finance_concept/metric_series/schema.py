import hashlib
from dataclasses import dataclass, field


@dataclass
class MetricGroup:
    group_id: str = ""
    metric_id: str = ""
    metric_name: str = ""
    report_period: str = ""
    status: str = ""
    candidate_count: int = 0
    selected_candidate_id: str = ""
    selection_method: str = ""
    value_normalized: float = 0.0
    value_unit_normalized: str = ""
    is_percent: bool = False
    review_reasons: list = field(default_factory=list)
    candidate_ids: list = field(default_factory=list)


@dataclass
class MetricSeriesPoint:
    series_id: str = ""
    metric_id: str = ""
    metric_name: str = ""
    report_period: str = ""
    period_year: int = 0
    period_type: str = ""
    period_order: int = 0
    value_normalized: float = 0.0
    value_unit_normalized: str = ""
    is_percent: bool = False
    source_candidate_id: str = ""
    source_pdf: str = ""
    page_number: int = 0
    selection_method: str = ""
    source_snippet: str = ""


def generate_group_id(metric_id: str, report_period: str) -> str:
    key = f"mg|{metric_id}|{report_period}"
    return f"mg_{hashlib.sha256(key.encode()).hexdigest()[:12]}"


def generate_series_id(group_id: str) -> str:
    return group_id.replace("mg_", "ms_", 1)


REQUIRED_CANDIDATE_FIELDS = [
    "candidate_id", "metric_id", "metric_name", "report_period",
    "value_normalized", "value_unit_normalized", "is_percent",
    "confidence", "needs_review", "source_pdf", "page_number",
    "source_snippet", "raw_value", "value",
]


def parse_period(period: str) -> tuple[int, str, int]:
    import re
    m = re.match(r"(\d{4})(Q[1-4]|H[1-2]|A)", period)
    if m:
        year = int(m.group(1))
        ptype = m.group(2)
        order = {"Q1": 1, "H1": 2, "Q2": 2, "Q3": 3, "H2": 4, "Q4": 4, "A": 4}.get(ptype, 0)
        return year, ptype, order
    return 0, "unknown", 0
