import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .errors import MetricExtractorError
from .schema import CSV_FIELDS, MetricCandidate


def write_metric_candidates_jsonl(
    candidates: list[MetricCandidate],
    output_file: Path,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_file.open("w", encoding="utf-8") as f:
            for c in candidates:
                d = asdict(c)
                json.dump(d, f, ensure_ascii=False)
                f.write("\n")
    except Exception as e:
        raise MetricExtractorError(f"Failed to write {output_file}: {e}") from e


def write_metric_candidates_csv(
    candidates: list[MetricCandidate],
    output_file: Path,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for c in candidates:
                d = asdict(c)
                row = {k: d.get(k, "") for k in CSV_FIELDS}
                row["review_reasons"] = "; ".join(d.get("review_reasons", []))
                writer.writerow(row)
    except Exception as e:
        raise MetricExtractorError(f"Failed to write {output_file}: {e}") from e


def write_metric_stats_json(
    candidates: list[MetricCandidate],
    manifest_pdfs: list[dict],
    warnings: list[str],
    output_file: Path,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    stats: dict = {
        "total_candidates": len(candidates),
        "needs_review_count": sum(1 for c in candidates if c.needs_review),
        "metrics": {},
        "warnings": warnings,
    }

    for c in candidates:
        mid = c.metric_id
        if mid not in stats["metrics"]:
            stats["metrics"][mid] = {
                "candidate_count": 0,
                "high_confidence_count": 0,
                "needs_review_count": 0,
                "periods": set(),
            }
        ms = stats["metrics"][mid]
        ms["candidate_count"] += 1
        if c.confidence == "high":
            ms["high_confidence_count"] += 1
        if c.needs_review:
            ms["needs_review_count"] += 1
        ms["periods"].add(c.report_period)

    for mid in stats["metrics"]:
        ms = stats["metrics"][mid]
        ms["periods"] = sorted(ms["periods"])

    try:
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=list)
    except Exception as e:
        raise MetricExtractorError(f"Failed to write {output_file}: {e}") from e


def write_metric_extraction_report(
    candidates: list[MetricCandidate],
    stats: dict,
    warnings: list[str],
    manifest_pdfs: list[dict],
    output_file: Path,
    concepts_file: str,
    pages_file: str,
    manifest_file: str,
    concepts_version: str,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    total_pages = sum(m.get("page_count", 0) for m in manifest_pdfs)
    pdf_count = len(manifest_pdfs)
    needs_review = sum(1 for c in candidates if c.needs_review)
    high_conf = sum(1 for c in candidates if c.confidence == "high")
    medium_conf = sum(1 for c in candidates if c.confidence == "medium")
    low_conf = sum(1 for c in candidates if c.confidence == "low")

    lines: list[str] = []
    lines.append("# 指标候选值抽取报告")
    lines.append("")
    lines.append("> 本轮结果是候选值，不是最终财务数据")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("## 输入文件")
    lines.append("")
    lines.append(f"- 概念库: `{concepts_file}` (版本: {concepts_version})")
    lines.append(f"- Pages: `{pages_file}`")
    lines.append(f"- Manifest: `{manifest_file}`")
    lines.append("")

    lines.append("## 总览")
    lines.append("")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"| --- | --- |")
    lines.append(f"| PDF 数量 | {pdf_count} |")
    lines.append(f"| 页面数量 | {total_pages} |")
    lines.append(f"| 总候选值 | {len(candidates)} |")
    lines.append(f"| 高置信 | {high_conf} |")
    lines.append(f"| 中置信 | {medium_conf} |")
    lines.append(f"| 低置信 | {low_conf} |")
    lines.append(f"| 需要复核 | {needs_review} |")
    lines.append("")

    if stats.get("metrics"):
        lines.append("## 按指标统计")
        lines.append("")
        lines.append("| metric_id | 候选数 | 高置信 | 需复核 | 报告期 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for mid in sorted(stats["metrics"].keys()):
            ms = stats["metrics"][mid]
            periods = ", ".join(ms.get("periods", []))
            lines.append(
                f"| {mid} | {ms['candidate_count']} | "
                f"{ms['high_confidence_count']} | {ms['needs_review_count']} | "
                f"{periods} |"
            )
        lines.append("")

    high_conf_candidates = [c for c in candidates if c.confidence == "high"]
    if high_conf_candidates:
        lines.append("## 高置信候选示例")
        lines.append("")
        for i, c in enumerate(high_conf_candidates[:5], 1):
            lines.append(f"**{i}.** `{c.metric_name}` → {c.raw_value} ({c.report_period})")
            lines.append(f"> {c.source_snippet}")
            lines.append("")

    review_candidates = [c for c in candidates if c.needs_review]
    if review_candidates:
        lines.append("## 需要复核的候选示例")
        lines.append("")
        for i, c in enumerate(review_candidates[:5], 1):
            reasons = "; ".join(c.review_reasons)
            lines.append(f"**{i}.** `{c.metric_name}` → {c.raw_value} (reason: {reasons})")
            lines.append(f"> {c.source_snippet}")
            lines.append("")

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in sorted(set(warnings)):
            lines.append(f"- {w}")
        lines.append("")

    try:
        output_file.write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        raise MetricExtractorError(f"Failed to write {output_file}: {e}") from e


HC_CSV_FIELDS = [
    "metric_id", "metric_name", "report_period", "source_pdf", "page_number",
    "matched_alias", "raw_value", "value_normalized", "value_unit_normalized",
    "unit_source", "confidence", "needs_review", "review_reasons", "source_snippet",
]


def write_high_confidence_table_csv(
    candidates: list[MetricCandidate],
    output_file: Path,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    filtered = [
        c for c in candidates
        if c.section_type
        and c.confidence in ("high", "medium")
        and c.value_normalized is not None
        and c.report_period != "unknown"
        and (c.value_unit_normalized != "unknown" or c.metric_id == "gross_margin")
    ]
    
    with output_file.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HC_CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for c in filtered:
            d = asdict(c)
            reasons = "; ".join(d.get("review_reasons", []))
            row = {k: reasons if k == "review_reasons" else d.get(k, "") for k in HC_CSV_FIELDS}
            w.writerow(row)
