import csv
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .errors import MetricSeriesError
from .schema import MetricGroup, MetricSeriesPoint, parse_period

LONG_CSV_FIELDS = [
    "metric_id", "metric_name", "report_period", "period_year", "period_type",
    "period_order", "value_normalized", "value_unit_normalized", "is_percent",
    "source_candidate_id", "source_pdf", "page_number", "selection_method",
]

REVIEW_QUEUE_FIELDS = [
    "group_id", "metric_id", "metric_name", "report_period", "status",
    "candidate_count", "candidate_ids", "review_reasons",
]


def write_metric_groups_jsonl(groups: list[MetricGroup], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for g in groups:
            json.dump(asdict(g), f, ensure_ascii=False)
            f.write("\n")


def write_metric_series_jsonl(series: list[MetricSeriesPoint], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for s in series:
            json.dump(asdict(s), f, ensure_ascii=False)
            f.write("\n")


def write_series_long_csv(series: list[MetricSeriesPoint], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LONG_CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for s in series:
            d = asdict(s)
            w.writerow({k: d.get(k, "") for k in LONG_CSV_FIELDS})


def write_series_wide_csv(series: list[MetricSeriesPoint], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    metric_ids = sorted({s.metric_id for s in series})
    periods: dict[tuple[int, int], dict] = {}

    for s in series:
        key = (s.period_year, s.period_order)
        if key not in periods:
            periods[key] = {
                "report_period": s.report_period,
                "period_year": s.period_year,
                "period_type": s.period_type,
                "period_order": s.period_order,
            }
        periods[key][s.metric_id] = s.value_normalized

    sorted_periods = sorted(periods.items())

    fieldnames = ["report_period", "period_year", "period_type", "period_order"] + metric_ids

    with output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for _, pd in sorted_periods:
            row = {k: pd.get(k, "") for k in fieldnames}
            w.writerow(row)


def write_review_queue_csv(groups: list[MetricGroup], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    queue = [g for g in groups if g.status != "selected"]
    with output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_QUEUE_FIELDS, extrasaction="ignore")
        w.writeheader()
        for g in queue:
            d = asdict(g)
            d["candidate_ids"] = "; ".join(g.candidate_ids)
            d["review_reasons"] = "; ".join(g.review_reasons)
            w.writerow({k: d.get(k, "") for k in REVIEW_QUEUE_FIELDS})


def write_series_report(
    groups: list[MetricGroup],
    series: list[MetricSeriesPoint],
    candidates_count: int,
    warnings: list[str],
    output: Path,
    candidates_file: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    selected_count = sum(1 for g in groups if g.status == "selected")
    needs_review_count = sum(1 for g in groups if g.status == "needs_review")
    conflict_count = sum(1 for g in groups if g.status == "conflict")
    empty_count = sum(1 for g in groups if g.status == "empty")

    lines: list[str] = []
    lines.append("# 指标时间序列报告")
    lines.append("")
    lines.append("> 本轮只生成可追溯时间序列候选，不做同比、CAGR、评分或投资判断")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("## 输入")
    lines.append("")
    lines.append(f"- Candidates: `{candidates_file}`")
    lines.append("")

    lines.append("## 总览")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"| --- | --- |")
    lines.append(f"| 候选值总数 | {candidates_count} |")
    lines.append(f"| 分组总数 | {len(groups)} |")
    lines.append(f"| selected | {selected_count} |")
    lines.append(f"| needs_review | {needs_review_count} |")
    lines.append(f"| conflict | {conflict_count} |")
    lines.append(f"| empty | {empty_count} |")
    lines.append(f"| 进入时间序列的指标数 | {len({s.metric_id for s in series})} |")
    lines.append(f"| 进入时间序列的报告期数 | {len({s.report_period for s in series})} |")

    selected_groups = [g for g in groups if g.status == "selected"]
    if selected_groups:
        lines.append("")
        lines.append("## Selected 分组")
        lines.append("")
        lines.append("| metric_id | report_period | value | method |")
        lines.append("| --- | --- | --- | --- |")
        for g in selected_groups:
            lines.append(
                f"| {g.metric_id} | {g.report_period} | {g.value_normalized} | {g.selection_method} |"
            )

    review_groups = [g for g in groups if g.status != "selected"]
    if review_groups:
        lines.append("")
        lines.append("## Review Queue")
        lines.append("")
        for g in review_groups:
            lines.append(f"- **{g.metric_id}** / {g.report_period}: {g.status}")
            if g.review_reasons:
                for r in g.review_reasons:
                    lines.append(f"  - {r}")
    lines.append("")

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")
