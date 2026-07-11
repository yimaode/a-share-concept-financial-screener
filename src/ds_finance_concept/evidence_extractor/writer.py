import csv
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .errors import EvidenceExtractorError
from .schema import EVIDENCE_CSV_FIELDS, EvidenceHit


def write_evidence_jsonl(hits: list[EvidenceHit], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_file.open("w", encoding="utf-8") as f:
            for hit in hits:
                d = asdict(hit)
                json.dump(d, f, ensure_ascii=False)
                f.write("\n")
    except Exception as e:
        raise EvidenceExtractorError(f"Failed to write {output_file}: {e}") from e


def write_evidence_csv(hits: list[EvidenceHit], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=EVIDENCE_CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for hit in hits:
                d = asdict(hit)
                row = {k: d.get(k, "") for k in EVIDENCE_CSV_FIELDS}
                writer.writerow(row)
    except Exception as e:
        raise EvidenceExtractorError(f"Failed to write {output_file}: {e}") from e


def write_concept_keyword_stats(stats: dict, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise EvidenceExtractorError(f"Failed to write {output_file}: {e}") from e


def write_evidence_report(
    hits: list[EvidenceHit],
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
    negation_count = sum(1 for h in hits if h.negation_detected)
    positive_count = sum(1 for h in hits if h.polarity == "positive")
    negative_count = sum(1 for h in hits if h.polarity == "negative")
    pdf_count = len(manifest_pdfs)

    lines: list[str] = []
    lines.append("# 财报证据抽取报告")
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
    lines.append(f"| 总命中数 | {len(hits)} |")
    lines.append(f"| 正向证据 | {positive_count} |")
    lines.append(f"| 负向证据 | {negative_count} |")
    lines.append(f"| 否定词命中 | {negation_count} |")
    lines.append("")

    if stats.get("concepts"):
        lines.append("## 按概念统计")
        lines.append("")
        lines.append("| concept_id | 名称 | 正向 | 负向 | 总数 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for cid, cs in sorted(stats["concepts"].items()):
            lines.append(
                f"| {cid} | {cs['concept_name']} | "
                f"{cs['positive_hits']} | {cs['negative_hits']} | "
                f"{cs['positive_hits'] + cs['negative_hits']} |"
            )
        lines.append("")

    for cid, cs in sorted((stats.get("concepts") or {}).items()):
        lines.append(f"## {cs['concept_name']} / {cid}")
        lines.append("")

        lines.append("### Top Keywords")
        lines.append("")
        top_kw = list(cs.get("keywords", {}).items())[:10]
        for kw, count in top_kw:
            lines.append(f"- **{kw}**: {count}")
        lines.append("")

        c_hits = [h for h in hits if h.concept_id == cid]
        if c_hits:
            lines.append("### 证据句示例")
            lines.append("")
            for i, h in enumerate(c_hits[:5], 1):
                lines.append(f"**{i}.** `[{h.polarity}]` *{h.source_pdf}* p.{h.page_number}")
                lines.append(f"> {h.sentence}")
                lines.append("")
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
        raise EvidenceExtractorError(f"Failed to write {output_file}: {e}") from e
