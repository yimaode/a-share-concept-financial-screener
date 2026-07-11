import csv
import json
from datetime import datetime
from pathlib import Path

from .schema import DETAIL_CSV_FIELDS, SCORE_CSV_FIELDS


def write_scores_json(data: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_scores_csv(concepts: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SCORE_CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for c in concepts:
            mc = c.get("metric_coverage", {})
            row = {
                "concept_id": c.get("concept_id", ""),
                "concept_name": c.get("concept_name", ""),
                "score": c.get("score", 0),
                "level": c.get("level", ""),
                "status": c.get("status", ""),
                "positive_hits": c.get("positive_hits", 0),
                "negative_hits": c.get("negative_hits", 0),
                "available_metrics": mc.get("available", 0),
                "missing_metrics": "; ".join(mc.get("missing", [])),
                "warnings": "; ".join(c.get("warnings", [])),
            }
            w.writerow(row)


def write_details_jsonl(details: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for d in details:
            json.dump(d, f, ensure_ascii=False)
            f.write("\n")


def write_score_report(
    scores_data: dict,
    warnings: list[str],
    output: Path,
    concepts_file: str,
    trends_file: str,
    evidence_file: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    concepts = scores_data.get("concepts", [])

    lines: list[str] = []
    lines.append("# 概念符合度评分报告")
    lines.append("")
    lines.append("> 本轮不是投资建议，不输出买卖结论")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"- 概念库: `{concepts_file}`")
    lines.append(f"- 趋势文件: `{trends_file}`")
    lines.append(f"- 证据文件: `{evidence_file}`")
    lines.append("")

    lines.append("## 概念得分总览")
    lines.append("")
    lines.append("| concept_id | 名称 | 分数 | Level | 正向证据 | 负向证据 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for c in concepts:
        lines.append(
            f"| {c['concept_id']} | {c['concept_name']} | {c['score']} | "
            f"{c['level']} | {c['positive_hits']} | {c['negative_hits']} |"
        )
    lines.append("")

    for c in concepts:
        lines.append(f"## {c['concept_name']} / {c['concept_id']}")
        lines.append("")
        lines.append(f"- 分数: **{c['score']}** ({c['level']})")
        lines.append(f"- 正向证据: {c['positive_hits']}")
        lines.append(f"- 负向证据: {c['negative_hits']}")
        mc = c.get("metric_coverage", {})
        lines.append(f"- 可用指标: {mc.get('available', 0)}/{mc.get('required', 0)}")
        if mc.get("missing"):
            lines.append(f"- 缺失指标: {', '.join(mc['missing'])}")
        lines.append("")
        if c.get("top_reasons"):
            lines.append("**Top Reasons:**")
            for r in c["top_reasons"]:
                lines.append(f"- {r}")
            lines.append("")

    lines.append("## 风险反证特别说明")
    lines.append("")
    lines.append("`risk_negative_evidence` 分数越高代表风险越强，不是正向投资分数。高分不等于投资价值高。")
    lines.append("")

    if warnings:
        lines.append("## Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")
