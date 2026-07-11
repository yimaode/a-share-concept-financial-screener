import csv
import json
from collections import defaultdict
from pathlib import Path

from .errors import CandidateValidationError, MetricSeriesError, ReviewDecisionError
from .schema import (
    MetricGroup,
    MetricSeriesPoint,
    REQUIRED_CANDIDATE_FIELDS,
    generate_group_id,
    generate_series_id,
    parse_period,
)

VALID_DECISIONS = {"approve", "reject"}


def _read_candidates(path: Path) -> list[dict]:
    if not path.exists():
        raise CandidateValidationError(f"Candidates file not found: {path}")
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                raise CandidateValidationError(
                    f"Invalid JSON at line {line_num} in {path}: {e}"
                ) from e
    return records


def _validate_candidates(candidates: list[dict]) -> list[str]:
    warnings: list[str] = []
    seen_ids: dict[str, dict] = {}

    for c in candidates:
        for field in REQUIRED_CANDIDATE_FIELDS:
            if field not in c:
                raise CandidateValidationError(
                    f"Candidate {c.get('candidate_id', 'unknown')} missing field: {field}"
                )

        cid = c["candidate_id"]
        if cid in seen_ids:
            prev = seen_ids[cid]
            if json.dumps(c, sort_keys=True, ensure_ascii=False) != json.dumps(prev, sort_keys=True, ensure_ascii=False):
                raise CandidateValidationError(
                    f"Duplicate candidate_id {cid} with different content"
                )
            warnings.append(f"Duplicate candidate_id {cid} (identical content, deduplicated)")
        seen_ids[cid] = c

    return warnings


def _read_review_decisions(path: Path) -> dict[str, dict]:
    if not path:
        return {}
    if not path.exists():
        raise ReviewDecisionError(f"Review decisions file not found: {path}")

    decisions: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ReviewDecisionError("Review decisions CSV has no header")
        for req in ("candidate_id", "decision"):
            if req not in (reader.fieldnames or []):
                raise ReviewDecisionError(f"Review decisions CSV missing column: {req}")

        for row_num, row in enumerate(reader, 2):
            cid = row.get("candidate_id", "").strip()
            decision = row.get("decision", "").strip().lower()
            note = row.get("reviewer_note", "")

            if not cid:
                raise ReviewDecisionError(f"Row {row_num}: empty candidate_id")
            if decision not in VALID_DECISIONS:
                raise ReviewDecisionError(
                    f"Row {row_num}: invalid decision {decision!r} for {cid}"
                )
            if cid in decisions and decisions[cid]["decision"] != decision:
                raise ReviewDecisionError(
                    f"Conflicting decisions for candidate_id {cid}"
                )
            decisions[cid] = {"decision": decision, "reviewer_note": note}

    return decisions


def _auto_select(candidates: list[dict]) -> tuple[str, str, float, str, bool, list[str]]:
    reasons: list[str] = []
    valid = [c for c in candidates if _is_auto_selectable(c)]

    if not valid:
        reasons.append("无满足自动选择条件的候选值")
        return "needs_review", "", 0.0, "", False, reasons

    for c in valid:
        if c.get("value_normalized", 0) == 0 and c.get("metric_id") in AMOUNT_METRICS:
            raw = c.get("raw_value", "")
            if raw.strip() not in ("0", "0.0", "0.00", "0.0 万元", "0 万元"):
                reasons.append(f"value_normalized=0 but raw_value is {raw!r}, needs review")
                return "needs_review", "", 0.0, "", False, reasons

        mid = c.get("metric_id", "")
        vn = c.get("value_normalized", 0)
        unit = c.get("value_unit_normalized", "")
        if mid in AMOUNT_METRICS and unit == "CNY" and abs(vn) > 0:
            if abs(vn) < MIN_PLAUSIBLE_CNY:
                snippet = c.get("source_snippet", "")
                if "亿元" not in snippet and "亿元" not in c.get("raw_value", ""):
                    reasons.append("implausibly_small_amount_for_listed_company")
                    return "needs_review", "", 0.0, "", False, reasons

    if len(valid) == 1:
        c = valid[0]
        return "selected", c["candidate_id"], c["value_normalized"], c["value_unit_normalized"], c.get("is_percent", False), []

    values = {c["value_normalized"] for c in valid}
    if len(values) == 1:
        c = valid[0]
        return "selected", c["candidate_id"], c["value_normalized"], c["value_unit_normalized"], c.get("is_percent", False), []

    reasons.append(f"多个候选值但数值不同: {sorted(values)}")
    return "conflict", "", 0.0, "", False, reasons


AMOUNT_METRICS = {
    "revenue", "net_profit_attributable", "deducted_net_profit",
    "operating_cashflow", "fixed_assets", "inventory",
    "contract_liabilities", "total_assets", "construction_in_progress",
    "rd_expense",
}

MIN_PLAUSIBLE_CNY = 1_000_000

SECTION_METRIC_MAP = {
    "income_statement": {"revenue", "net_profit_attributable", "deducted_net_profit", "rd_expense"},
    "balance_sheet": {"total_assets", "inventory", "contract_liabilities", "fixed_assets", "construction_in_progress"},
    "cashflow_statement": {"operating_cashflow"},
    "key_financial_data": set(),
}


def _is_auto_selectable(c: dict) -> bool:
    mid = c.get("metric_id", "")
    vn = c.get("value_normalized")
    unit = c.get("value_unit_normalized", "")

    if c.get("confidence") not in ("high", "medium"):
        return False
    if c.get("needs_review"):
        return False
    if c.get("report_period") == "unknown":
        return False
    if vn is None:
        return False
    if unit == "unknown":
        return False
    if mid == "gross_margin" and not c.get("is_percent"):
        return False
    if mid in AMOUNT_METRICS and unit != "CNY":
        return False
    if mid not in ("operating_cashflow", "net_profit_attributable", "deducted_net_profit") and mid in AMOUNT_METRICS and abs(vn) <= 0:
        return False

    if c.get("column_role") and c.get("column_role") != "current_period":
        return False

    section_type = c.get("section_type", "")
    if section_type and section_type in SECTION_METRIC_MAP:
        allowed = SECTION_METRIC_MAP.get(section_type, set())
        if allowed and mid not in allowed:
            return False

    return True


def _apply_review_decisions(
    candidates: list[dict],
    decisions: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    active: list[dict] = []
    rejected: list[dict] = []
    approved: list[dict] = []

    for c in candidates:
        cid = c["candidate_id"]
        dec = decisions.get(cid)
        if dec and dec["decision"] == "reject":
            rejected.append(c)
        elif dec and dec["decision"] == "approve":
            approved.append(c)
        else:
            active.append(c)

    if len(approved) > 1:
        unique_vals = {c["value_normalized"] for c in approved}
        if len(unique_vals) > 1:
            raise ReviewDecisionError(
                f"Multiple approved candidates in group with different values"
            )

    return active, approved


def build_metric_series(
    candidates_file: Path,
    review_decisions_file: Path | None = None,
    manual_series_file: Path | None = None,
) -> tuple[list[MetricGroup], list[MetricSeriesPoint], list[str]]:
    candidates = _read_candidates(candidates_file)
    warnings = _validate_candidates(candidates)

    decisions = _read_review_decisions(review_decisions_file) if review_decisions_file else {}

    for cid in decisions:
        if cid not in {c["candidate_id"] for c in candidates}:
            raise ReviewDecisionError(
                f"Review decision references unknown candidate_id: {cid}"
            )

    cid_to_candidate = {c["candidate_id"]: c for c in candidates}
    unique_candidates = list(cid_to_candidate.values())

    manual_series = []
    if manual_series_file and manual_series_file.exists():
        with manual_series_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    manual_series.append(json.loads(line))

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in unique_candidates:
        key = (c["metric_id"], c["report_period"])
        groups[key].append(c)

    metric_groups: list[MetricGroup] = []
    metric_series: list[MetricSeriesPoint] = []

    for (metric_id, report_period), group_candidates in sorted(groups.items()):
        metric_name = group_candidates[0].get("metric_name", metric_id)
        group_id = generate_group_id(metric_id, report_period)
        all_cids = sorted({c["candidate_id"] for c in group_candidates})

        active, approved = _apply_review_decisions(group_candidates, decisions)

        status = ""
        selected_cid = ""
        selection_method = ""
        val = 0.0
        unit = ""
        is_pct = False
        reasons: list[str] = []

        if len(approved) == 1:
            c = approved[0]
            status = "selected"
            selected_cid = c["candidate_id"]
            selection_method = "manual_approved"
            val = c["value_normalized"] or 0.0
            unit = c.get("value_unit_normalized", "")
            is_pct = c.get("is_percent", False)
            reasons = []
        elif len(approved) > 1:
            status = "conflict"
            reasons = ["多个候选值被手动 approve，且数值不同"]
        else:
            status, selected_cid, val, unit, is_pct, reasons = _auto_select(active)
            if status == "selected":
                selection_method = "auto_unique"

        mg = MetricGroup(
            group_id=group_id,
            metric_id=metric_id,
            metric_name=metric_name,
            report_period=report_period,
            status=status,
            candidate_count=len(group_candidates),
            selected_candidate_id=selected_cid,
            selection_method=selection_method,
            value_normalized=val,
            value_unit_normalized=unit,
            is_percent=is_pct,
            review_reasons=reasons,
            candidate_ids=all_cids,
        )
        metric_groups.append(mg)

        if mg.status == "selected" and selected_cid:
            selected = candidates_by_id(cid_to_candidate, selected_cid)
            if selected and report_period != "unknown":
                year, ptype, order = parse_period(report_period)
                metric_series.append(MetricSeriesPoint(
                    series_id=generate_series_id(group_id),
                    metric_id=metric_id,
                    metric_name=metric_name,
                    report_period=report_period,
                    period_year=year,
                    period_type=ptype,
                    period_order=order,
                    value_normalized=mg.value_normalized,
                    value_unit_normalized=mg.value_unit_normalized,
                    is_percent=mg.is_percent,
                    source_candidate_id=mg.selected_candidate_id,
                    source_pdf=selected.get("source_pdf", ""),
                    page_number=selected.get("page_number", 0),
                    selection_method=mg.selection_method or "auto_unique",
                    source_snippet=selected.get("source_snippet", ""),
                ))

    metric_series.sort(key=lambda ms: (
        ms.metric_id,
        ms.period_year,
        ms.period_order,
    ))

    metric_groups = _check_magnitude_jumps(metric_groups)

    for man in manual_series:
        mid = man.get("metric_id", "")
        period = man.get("report_period", "")
        group_id = generate_group_id(mid, period)
        mg = MetricGroup(
            group_id=group_id, metric_id=mid, metric_name=man.get("metric_name", mid),
            report_period=period, status="selected",
            candidate_count=1, selected_candidate_id="manual",
            selection_method="manual_review",
            value_normalized=man.get("value_normalized", 0),
            value_unit_normalized=man.get("value_unit_normalized", ""),
            is_percent=man.get("is_percent", False),
            candidate_ids=[],
        )
        metric_groups.append(mg)
        year, ptype, order = parse_period(period)
        metric_series.append(MetricSeriesPoint(
            series_id=generate_series_id(group_id), metric_id=mid,
            metric_name=man.get("metric_name", mid), report_period=period,
            period_year=year, period_type=ptype, period_order=order,
            value_normalized=man.get("value_normalized", 0),
            value_unit_normalized=man.get("value_unit_normalized", ""),
            is_percent=man.get("is_percent", False),
            source_candidate_id="manual",
            source_pdf=man.get("source_pdf", ""), page_number=man.get("page_number", 0),
            selection_method="manual_review", source_snippet=man.get("source_snippet", ""),
        ))

    demoted_group_ids = {g.group_id for g in metric_groups if g.status != "selected"}
    metric_series = [ms for ms in metric_series if ms.series_id not in demoted_group_ids]

    series_deduped = {}
    for ms in metric_series:
        key = (ms.metric_id, ms.report_period)
        if key in series_deduped:
            exist = series_deduped[key]
            priority = {"web_api": 3, "manual_review": 3, "manual_approved": 3, "auto_unique": 1, "": 0}
            if priority.get(ms.selection_method, 0) > priority.get(exist.selection_method, 0):
                series_deduped[key] = ms
        else:
            series_deduped[key] = ms
    metric_series = sorted(series_deduped.values(), key=lambda ms: (ms.metric_id, ms.period_year, ms.period_order))

    return metric_groups, metric_series, warnings


def _check_magnitude_jumps(groups: list[MetricGroup]) -> list[MetricGroup]:
    by_metric: dict[str, list[int]] = defaultdict(list)
    for i, g in enumerate(groups):
        if g.status == "selected":
            by_metric[g.metric_id].append(i)

    for metric_id, indices in by_metric.items():
        if len(indices) < 2:
            continue
        for j in range(1, len(indices)):
            prev = groups[indices[j - 1]]
            curr = groups[indices[j]]
            if prev.value_normalized == 0 or curr.value_normalized == 0:
                continue
            ratio = max(prev.value_normalized, curr.value_normalized) / min(prev.value_normalized, curr.value_normalized)
            if ratio > 10:
                prev_idx = indices[j - 1]
                curr_idx = indices[j]
                groups[prev_idx].status = "needs_review"
                groups[prev_idx].review_reasons.append("cross_period_magnitude_jump")
                groups[curr_idx].status = "needs_review"
                groups[curr_idx].review_reasons.append("cross_period_magnitude_jump")

    return groups


def candidates_by_id(mapping: dict[str, dict], cid: str) -> dict | None:
    return mapping.get(cid)
