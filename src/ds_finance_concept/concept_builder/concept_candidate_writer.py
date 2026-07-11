import json
from pathlib import Path
from datetime import datetime

from .concept_candidate_schema import ConceptCandidate, concept_candidate_to_dict
from .errors import JsonlWriteError


def write_concept_candidates_json(
    candidates: list[ConceptCandidate],
    output_file: Path,
    source_file: str,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    concepts_data = [concept_candidate_to_dict(cc) for cc in candidates]

    output = {
        "version": "0.1.0",
        "source_file": source_file,
        "concepts": concepts_data,
    }

    try:
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise JsonlWriteError(f"Failed to write JSON to {output_file}: {e}") from e


def _build_review_md(candidates: list[ConceptCandidate]) -> str:
    lines: list[str] = []
    lines.append("# 候选概念审核报告")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    total = len(candidates)
    needs_review = sum(1 for c in candidates if c.needs_manual_review)
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 总候选概念数：{total}")
    lines.append(f"- 需人工审核：{needs_review}")
    lines.append("")

    if candidates:
        lines.append("| 概念 ID | 名称 | 证据数 | 置信度(H/M/L) | 需审核 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for cc in candidates:
            cs = cc.confidence_summary
            conf_str = f"{cs.get('high', 0)}/{cs.get('medium', 0)}/{cs.get('low', 0)}"
            review_flag = "是" if cc.needs_manual_review else "否"
            lines.append(
                f"| {cc.candidate_concept_id} | {cc.canonical_name} "
                f"| {cc.evidence_count} | {conf_str} | {review_flag} |"
            )
        lines.append("")

    for cc in candidates:
        lines.append(f"## 候选概念：{cc.canonical_name}")
        lines.append("")

        lines.append("### 定义草稿")
        lines.append("")
        if cc.summary_definition:
            lines.append(cc.summary_definition)
        else:
            lines.append("（待人工定义）")
        lines.append("")

        lines.append("### 来源 Insight")
        lines.append("")
        for iid in cc.source_insight_ids:
            lines.append(f"- `{iid}`")
        lines.append("")

        lines.append("### 来源 Quote ID")
        lines.append("")
        for qid in cc.source_quote_ids:
            lines.append(f"- `{qid}`")
        lines.append("")

        lines.append("### 可观察信号")
        lines.append("")
        if cc.common_observable_signals:
            for signal in cc.common_observable_signals:
                lines.append(f"- {signal}")
        else:
            lines.append("（无）")
        lines.append("")

        lines.append("### 候选财务指标")
        lines.append("")
        if cc.common_financial_metrics:
            for metric in cc.common_financial_metrics:
                lines.append(f"- `{metric}`")
        else:
            lines.append("（无）")
        lines.append("")

        lines.append("### 候选财报关键词")
        lines.append("")
        if cc.common_report_keywords:
            for kw in cc.common_report_keywords:
                lines.append(f"- {kw}")
        else:
            lines.append("（无）")
        lines.append("")

        lines.append("### 不可量化部分")
        lines.append("")
        if cc.common_not_quantifiable_parts:
            for part in cc.common_not_quantifiable_parts:
                lines.append(f"- {part}")
        else:
            lines.append("（无）")
        lines.append("")

        lines.append("### 置信度统计")
        lines.append("")
        cs = cc.confidence_summary
        lines.append(f"- high: {cs.get('high', 0)}")
        lines.append(f"- medium: {cs.get('medium', 0)}")
        lines.append(f"- low: {cs.get('low', 0)}")
        lines.append("")

        lines.append("### 人工审核项")
        lines.append("")
        if cc.manual_review_reasons:
            for reason in cc.manual_review_reasons:
                lines.append(f"- **审核原因**: {reason}")
            lines.append("")
        lines.append("- [ ] 接受")
        lines.append("- [ ] 修改")
        lines.append("- [ ] 删除")
        lines.append("")

    return "\n".join(lines)


def write_concept_candidates_review_md(
    candidates: list[ConceptCandidate],
    output_file: Path,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    content = _build_review_md(candidates)
    try:
        output_file.write_text(content, encoding="utf-8")
    except Exception as e:
        raise JsonlWriteError(f"Failed to write review to {output_file}: {e}") from e
