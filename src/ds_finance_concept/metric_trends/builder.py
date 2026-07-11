import json
from collections import defaultdict
from pathlib import Path

from .errors import MetricTrendsError
from .schema import (
    MetricTrend,
    REQUIRED_SERIES_FIELDS,
    VALID_PERIOD_TYPES,
    generate_trend_id,
)


def _read_series(path: Path) -> list[dict]:
    if not path.exists():
        raise MetricTrendsError(f"Series file not found: {path}")
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                raise MetricTrendsError(
                    f"Invalid JSON at line {line_num} in {path}: {e}"
                ) from e
    return records


def _validate_series(records: list[dict]) -> list[str]:
    warnings: list[str] = []
    seen: dict[tuple, dict] = {}
    seen_dups: set = set()

    for r in records:
        for field in REQUIRED_SERIES_FIELDS:
            if field not in r:
                raise MetricTrendsError(
                    f"Series {r.get('series_id', 'unknown')} missing field: {field}"
                )

        period = r.get("report_period", "")
        if period == "unknown":
            raise MetricTrendsError("Unknown report_period not allowed in series file")

        key = (r["metric_id"], r["report_period"])
        val = r.get("value_normalized")
        method = r.get("selection_method", "")
        if key in seen:
            prev = seen[key]
            prev_method = prev.get("selection_method", "")
            prev_val = prev.get("value_normalized")
            if prev_val != val:
                manual_priority = {"web_api": 3, "manual_review": 3, "manual_approved": 3, "auto_unique": 1, "": 0}
                if manual_priority.get(method, 0) > manual_priority.get(prev_method, 0):
                    seen[key] = r
                    warnings.append(f"Duplicate {r['metric_id']}/{r['report_period']}: web/manual value preferred")
                elif manual_priority.get(method, 0) < manual_priority.get(prev_method, 0):
                    pass
                else:
                    raise MetricTrendsError(
                        f"Conflicting values for {r['metric_id']}/{r['report_period']}"
                    )
            if key not in seen_dups:
                warnings.append(f"Duplicate {r['metric_id']}/{r['report_period']} (deduplicated)")
                seen_dups.add(key)
        else:
            seen[key] = r

    return warnings


def _compute_yoy(
    current: dict,
    prev_same_period: dict | None,
) -> tuple[float | None, float | None, str, str, str]:
    if prev_same_period is None:
        return None, None, "", "missing_base", "missing previous year same period"

    if current.get("value_unit_normalized") != prev_same_period.get("value_unit_normalized"):
        return None, None, "", "unit_mismatch", "unit mismatch"

    prev_val = prev_same_period.get("value_normalized", 0)
    if prev_val == 0:
        return None, None, prev_same_period["report_period"], "previous_value_zero", "previous value is zero"

    cur_val = current["value_normalized"]
    is_pct = current.get("is_percent", False)

    if is_pct:
        change_pp = cur_val - prev_val
        return None, change_pp, prev_same_period["report_period"], "computed", ""
    else:
        yoy = (cur_val - prev_val) / abs(prev_val)
        return yoy, None, prev_same_period["report_period"], "computed", ""


def _compute_sequential(
    current: dict,
    prev_point: dict | None,
) -> tuple[float | None, float | None, str, str, str]:
    if prev_point is None:
        return None, None, "", "missing_base", "no previous selected point"

    if current.get("value_unit_normalized") != prev_point.get("value_unit_normalized"):
        return None, None, "", "unit_mismatch", "unit mismatch"

    prev_val = prev_point.get("value_normalized", 0)
    if prev_val == 0:
        return None, None, prev_point["report_period"], "previous_value_zero", "previous value is zero"

    cur_val = current["value_normalized"]
    is_pct = current.get("is_percent", False)

    if is_pct:
        change_pp = cur_val - prev_val
        return None, change_pp, prev_point["report_period"], "computed", ""
    else:
        change = (cur_val - prev_val) / abs(prev_val)
        return change, None, prev_point["report_period"], "computed", ""


def _compute_cagr_3y(
    current: dict,
    prev_3y: dict | None,
) -> tuple[float | None, str, str, str]:
    if current.get("is_percent"):
        return None, "", "not_applicable", "cagr not applicable for percentage metrics"

    if current.get("report_period", "").endswith("A") is False or "A" not in current.get("period_type", ""):
        return None, "", "not_applicable", "not annual period"

    if prev_3y is None:
        return None, "", "insufficient_history", "no data from 3 years ago"

    if current.get("value_unit_normalized") != prev_3y.get("value_unit_normalized"):
        return None, "", "unit_mismatch", "unit mismatch"

    cur_val = current["value_normalized"]
    prev_val = prev_3y["value_normalized"]

    if cur_val <= 0 or prev_val <= 0:
        return None, prev_3y.get("report_period", ""), "non_positive_value", "values must be positive for CAGR"

    cagr = (cur_val / prev_val) ** (1 / 3) - 1
    return cagr, prev_3y.get("report_period", ""), "computed", ""


def _compute_consecutive_growth(
    current: dict,
    prev_point: dict | None,
    prev_count: int,
) -> tuple[int, str, str]:
    if prev_point is None:
        return 0, "computed", ""

    if current.get("value_unit_normalized") != prev_point.get("value_unit_normalized"):
        return 0, "unit_mismatch", "unit mismatch"

    cur_val = current["value_normalized"]
    prev_val = prev_point["value_normalized"]

    if cur_val > prev_val:
        return prev_count + 1, "computed", ""
    else:
        return 0, "computed", ""


def compute_trends(series_file: Path) -> tuple[list[MetricTrend], list[str]]:
    records = _read_series(series_file)
    warnings = _validate_series(records)

    deduped: dict[tuple, dict] = {}
    for r in records:
        key = (r["metric_id"], r["report_period"])
        deduped[key] = r

    by_metric: dict[str, list[dict]] = defaultdict(list)
    for r in deduped.values():
        by_metric[r["metric_id"]].append(r)

    trends: list[MetricTrend] = []

    for metric_id, points in sorted(by_metric.items()):
        metric_name = points[0].get("metric_name", metric_id)
        is_pct = points[0].get("is_percent", False)

        points.sort(key=lambda p: (p["period_year"], p["period_order"]))

        growth_count = 0

        for i, cur in enumerate(points):
            report_period = cur["report_period"]
            period_year = cur["period_year"]
            period_type = cur["period_type"]
            period_order_val = cur["period_order"]
            trend_id = generate_trend_id(metric_id, report_period)

            prev_same = next(
                (p for p in points
                 if p.get("period_type") == period_type
                 and p.get("period_year") == period_year - 1),
                None,
            )

            yoy, change_pp, yoy_base, yoy_status, yoy_reason = _compute_yoy(cur, prev_same)

            prev_point_all = points[i - 1] if i > 0 else None
            seq, seq_pp, seq_base, seq_status, seq_reason = _compute_sequential(cur, prev_point_all)

            cagr_3y, cagr_base, cagr_status, cagr_reason = _compute_cagr_3y(
                cur,
                next((p for p in points
                      if p.get("period_type") == "A"
                      and p.get("period_year") == period_year - 3), None),
            )

            growth_count, growth_status, growth_reason = _compute_consecutive_growth(
                cur, prev_point_all, growth_count,
            )

            trends.append(MetricTrend(
                trend_id=trend_id,
                metric_id=metric_id,
                metric_name=metric_name,
                report_period=report_period,
                period_year=period_year,
                period_type=period_type,
                period_order=period_order_val,
                value_normalized=cur["value_normalized"],
                value_unit_normalized=cur.get("value_unit_normalized", ""),
                is_percent=is_pct,
                yoy=yoy,
                change_pp=change_pp,
                yoy_base_period=yoy_base,
                yoy_status=yoy_status,
                yoy_reason=yoy_reason,
                sequential_change=seq,
                sequential_change_pp=seq_pp,
                sequential_base_period=seq_base,
                sequential_status=seq_status,
                sequential_reason=seq_reason,
                cagr_3y=cagr_3y,
                cagr_3y_base_period=cagr_base,
                cagr_3y_status=cagr_status,
                cagr_3y_reason=cagr_reason,
                consecutive_growth_count=growth_count,
                growth_status=growth_status,
                growth_reason=growth_reason,
                source_series_id=cur.get("series_id", ""),
                source_candidate_id=cur.get("source_candidate_id", ""),
                source_pdf=cur.get("source_pdf", ""),
                page_number=cur.get("page_number", 0),
            ))

    return trends, warnings
