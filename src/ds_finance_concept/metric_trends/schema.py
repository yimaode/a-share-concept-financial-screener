import hashlib
from dataclasses import dataclass, field


@dataclass
class MetricTrend:
    trend_id: str = ""
    metric_id: str = ""
    metric_name: str = ""
    report_period: str = ""
    period_year: int = 0
    period_type: str = ""
    period_order: int = 0
    value_normalized: float = 0.0
    value_unit_normalized: str = ""
    is_percent: bool = False

    yoy: float | None = None
    change_pp: float | None = None
    yoy_base_period: str = ""
    yoy_status: str = ""
    yoy_reason: str = ""

    sequential_change: float | None = None
    sequential_change_pp: float | None = None
    sequential_base_period: str = ""
    sequential_status: str = ""
    sequential_reason: str = ""

    cagr_3y: float | None = None
    cagr_3y_base_period: str = ""
    cagr_3y_status: str = ""
    cagr_3y_reason: str = ""

    consecutive_growth_count: int = 0
    growth_status: str = ""
    growth_reason: str = ""

    source_series_id: str = ""
    source_candidate_id: str = ""
    source_pdf: str = ""
    page_number: int = 0


def generate_trend_id(metric_id: str, report_period: str) -> str:
    key = f"mt|{metric_id}|{report_period}"
    return f"mt_{hashlib.sha256(key.encode()).hexdigest()[:12]}"


REQUIRED_SERIES_FIELDS = [
    "series_id", "metric_id", "metric_name", "report_period",
    "period_year", "period_type", "period_order",
    "value_normalized", "value_unit_normalized", "is_percent",
    "source_candidate_id", "source_pdf", "page_number",
]

VALID_PERIOD_TYPES = {"Q1", "Q2", "H1", "Q3", "Q4", "A"}

TREND_LONG_CSV_FIELDS = [
    "metric_id", "metric_name", "report_period", "period_year",
    "period_type", "period_order", "value_normalized",
    "value_unit_normalized", "is_percent",
    "yoy", "change_pp", "sequential_change", "sequential_change_pp",
    "cagr_3y", "consecutive_growth_count",
    "source_series_id", "source_pdf", "page_number",
]
