import csv
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .schema import MetricTrend, TREND_LONG_CSV_FIELDS


def write_trends_jsonl(trends: list[MetricTrend], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for t in trends:
            json.dump(asdict(t), f, ensure_ascii=False)
            f.write("\n")


def write_trends_long_csv(trends: list[MetricTrend], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TREND_LONG_CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for t in trends:
            d = asdict(t)
            w.writerow({k: d.get(k, "") for k in TREND_LONG_CSV_FIELDS})


def write_trends_wide_csv(trends: list[MetricTrend], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    metric_ids = sorted({t.metric_id for t in trends})
    periods: dict[tuple, dict] = {}

    for t in trends:
        key = (t.period_year, t.period_order)
        if key not in periods:
            periods[key] = {
                "report_period": t.report_period,
                "period_year": t.period_year,
                "period_type": t.period_type,
                "period_order": t.period_order,
            }
        periods[key][t.metric_id] = t.value_normalized
        periods[key][f"{t.metric_id}__yoy"] = t.yoy
        periods[key][f"{t.metric_id}__change_pp"] = t.change_pp
        periods[key][f"{t.metric_id}__seq"] = t.sequential_change
        periods[key][f"{t.metric_id}__cagr_3y"] = t.cagr_3y
        periods[key][f"{t.metric_id}__growth_count"] = t.consecutive_growth_count

    cols = [f"{m}{s}" for m in metric_ids for s in
            ["", "__yoy", "__change_pp", "__seq", "__cagr_3y", "__growth_count"]]
    fieldnames = ["report_period", "period_year", "period_type", "period_order"] + cols

    with output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for _, pd in sorted(periods.items()):
            row = {k: pd.get(k, "") for k in fieldnames}
            w.writerow(row)


def write_trend_summary(trends: list[MetricTrend], warnings: list[str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    by_metric = defaultdict(list)
    for t in trends:
        by_metric[t.metric_id].append(t)

    summary: dict = {
        "total_trend_points": len(trends),
        "metrics": {},
        "warnings": warnings,
    }

    for mid, pts in sorted(by_metric.items()):
        latest = pts[-1]
        summary["metrics"][mid] = {
            "points": len(pts),
            "latest_period": latest.report_period,
            "latest_value": latest.value_normalized,
            "latest_yoy": latest.yoy,
            "latest_cagr_3y": latest.cagr_3y,
            "latest_consecutive_growth_count": latest.consecutive_growth_count,
            "available_periods": [p.report_period for p in pts],
        }

    with output.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def write_trend_report(
    trends: list[MetricTrend],
    warnings: list[str],
    output: Path,
    series_file: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    yoy_computed = sum(1 for t in trends if t.yoy_status == "computed")
    yoy_missing = sum(1 for t in trends if t.yoy_status == "missing_base")
    cagr_computed = sum(1 for t in trends if t.cagr_3y_status == "computed")
    metric_count = len({t.metric_id for t in trends})
    period_count = len({t.report_period for t in trends})

    lines: list[str] = []
    lines.append("# 指标趋势报告")
    lines.append("")
    lines.append("> 本轮只计算财务衍生指标，不做概念评分或投资判断")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"- 输入文件: `{series_file}`")
    lines.append(f"- 趋势点数量: {len(trends)}")
    lines.append(f"- 指标数量: {metric_count}")
    lines.append(f"- 报告期数量: {period_count}")
    lines.append(f"- 可计算同比: {yoy_computed}")
    lines.append(f"- 缺失同比基期: {yoy_missing}")
    lines.append(f"- 可计算 CAGR: {cagr_computed}")
    lines.append("")

    if trends:
        lines.append("## 按指标摘要")
        lines.append("")
        lines.append("| metric_id | 点数 | 最新值 | 最新同比 | 最新 CAGR | 连续增长 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        by_metric = defaultdict(list)
        for t in trends:
            by_metric[t.metric_id].append(t)
        for mid in sorted(by_metric):
            pts = by_metric[mid]
            latest = pts[-1]
            lines.append(
                f"| {mid} | {len(pts)} | {latest.value_normalized} | "
                f"{latest.yoy} | {latest.cagr_3y} | {latest.consecutive_growth_count} |"
            )
        lines.append("")

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")
