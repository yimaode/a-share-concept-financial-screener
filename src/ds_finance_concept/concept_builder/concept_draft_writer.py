import json
from datetime import datetime
from pathlib import Path

from .errors import JsonlWriteError


def _yaml_str(value: str) -> str:
    if any(ch in value for ch in (":", "#", "{", "}", "[", "]", ",", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`")):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _yaml_value(data, indent: int = 0) -> str:
    prefix = "  " * indent

    if isinstance(data, dict):
        if not data:
            return "{}"
        lines: list[str] = []
        for key, value in data.items():
            key_str = _yaml_str(str(key))
            if isinstance(value, dict):
                lines.append(f"{prefix}{key_str}:")
                lines.append(_yaml_value(value, indent + 1))
            elif isinstance(value, list):
                if not value:
                    lines.append(f"{prefix}{key_str}: []")
                else:
                    lines.append(f"{prefix}{key_str}:")
                    for item in value:
                        if isinstance(item, dict):
                            lines.append(f"{prefix}  -")
                            lines.append(_yaml_value(item, indent + 2))
                        else:
                            lines.append(f"{prefix}  - {_yaml_str(str(item))}")
            elif isinstance(value, bool):
                lines.append(f"{prefix}{key_str}: {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                lines.append(f"{prefix}{key_str}: {value}")
            elif value is None:
                lines.append(f"{prefix}{key_str}:")
            else:
                lines.append(f"{prefix}{key_str}: {_yaml_str(str(value))}")
        return "\n".join(lines)
    elif isinstance(data, list):
        if not data:
            return "[]"
        lines = []
        for item in data:
            if isinstance(item, dict):
                lines.append(f"{prefix}-")
                lines.append(_yaml_value(item, indent + 1))
            else:
                lines.append(f"{prefix}- {_yaml_str(str(item))}")
        return "\n".join(lines)
    else:
        return _yaml_str(str(data))


def write_concepts_draft_json(
    concepts: list[dict],
    output_file: Path,
    source_file: str,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "version": "0.1.0",
        "market": "A-share",
        "strategy_focus": "super_growth",
        "language": "zh-CN",
        "status": "draft",
        "generated_from": source_file,
        "concepts": _prepare_json_concepts(concepts),
    }

    try:
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise JsonlWriteError(f"Failed to write JSON to {output_file}: {e}") from e


def _prepare_json_concepts(concepts: list[dict]) -> list[dict]:
    result = []
    for c in concepts:
        result.append({
            "concept_id": c["concept_id"],
            "name": c["name"],
            "status": "draft",
            "definition": c.get("definition", ""),
            "aliases": c.get("aliases", []),
            "source_quote_ids": c.get("source_quote_ids", []),
            "positive_keywords": c.get("positive_keywords", {}),
            "negative_keywords": c.get("negative_keywords", {}),
            "hard_metrics": c.get("hard_metrics", []),
            "evidence_rules": c.get("evidence_rules", {}),
            "scoring": c.get("scoring", {}),
            "evidence_count": c.get("evidence_count", 0),
            "manual_review": c.get("manual_review", {
                "required": True,
                "status": "pending",
                "reason": "",
                "evidence_count": 0,
                "notes": [],
            }),
        })
    return result


def write_concepts_draft_yaml(
    concepts: list[dict],
    output_file: Path,
    source_file: str,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    top_lines: list[str] = []
    top_lines.append('version: "0.1.0"')
    top_lines.append('market: "A-share"')
    top_lines.append('strategy_focus: "super_growth"')
    top_lines.append('status: "draft"')
    top_lines.append(f'generated_from: {_yaml_str(source_file)}')
    top_lines.append("concepts:")

    for concept in concepts:
        c = concept
        top_lines.append(f"  - concept_id: {_yaml_str(c['concept_id'])}")
        top_lines.append(f"    name: {_yaml_str(c['name'])}")
        top_lines.append("    status: draft")
        top_lines.append(f"    definition: {_yaml_str(c['definition'])}")

        sqids = c.get("source_quote_ids", [])
        if sqids:
            top_lines.append("    source_quote_ids:")
            for qid in sqids:
                top_lines.append(f"      - {_yaml_str(qid)}")
        else:
            top_lines.append("    source_quote_ids: []")

        aliases = c.get("aliases", [])
        if aliases:
            top_lines.append("    aliases:")
            for alias in aliases:
                top_lines.append(f"      - {_yaml_str(alias)}")
        else:
            top_lines.append("    aliases: []")

        top_lines.append("    positive_keywords:")
        pk = c.get("positive_keywords", {})
        for group, words in pk.items():
            top_lines.append(f"      {_yaml_str(group)}:")
            for w in words:
                top_lines.append(f"        - {_yaml_str(w)}")

        top_lines.append("    negative_keywords:")
        nk = c.get("negative_keywords", {})
        for group, words in nk.items():
            top_lines.append(f"      {_yaml_str(group)}:")
            for w in words:
                top_lines.append(f"        - {_yaml_str(w)}")

        top_lines.append("    hard_metrics:")
        for m in c.get("hard_metrics", []):
            top_lines.append(f"      - {_yaml_str(m)}")

        top_lines.append("    evidence_rules:")
        er = c.get("evidence_rules", {})
        for er_key, er_val in er.items():
            if isinstance(er_val, bool):
                top_lines.append(f"      {_yaml_str(er_key)}: {'true' if er_val else 'false'}")
            else:
                top_lines.append(f"      {_yaml_str(er_key)}: {er_val}")

        top_lines.append("    scoring:")
        sc = c.get("scoring", {})
        for sc_key, sc_val in sc.items():
            top_lines.append(f"      {_yaml_str(sc_key)}: {sc_val}")

        mr = c.get("manual_review", {})
        top_lines.append("    manual_review:")
        top_lines.append(f"      required: {'true' if mr.get('required', True) else 'false'}")
        top_lines.append(f"      status: {_yaml_str(mr.get('status', 'pending'))}")
        top_lines.append(f"      reason: {_yaml_str(mr.get('reason', ''))}")
        top_lines.append(f"      evidence_count: {mr.get('evidence_count', 0)}")

    output_content = "\n".join(top_lines) + "\n"
    try:
        output_file.write_text(output_content, encoding="utf-8")
    except Exception as e:
        raise JsonlWriteError(f"Failed to write YAML to {output_file}: {e}") from e


def write_concept_review_md(
    concepts: list[dict],
    output_file: Path,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# 概念草案审核报告")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append("## 总览")
    lines.append("")
    lines.append("| concept_id | 名称 | 证据数量 | 是否需人工审核 | 原因 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for c in concepts:
        mr = c.get("manual_review", {})
        review_flag = "是" if mr.get("required", True) else "否"
        reason = mr.get("reason", "").replace("|", "/")
        lines.append(
            f"| {c['concept_id']} | {c['name']} | "
            f"{c.get('evidence_count', 0)} | {review_flag} | {reason} |"
        )
    lines.append("")

    for idx, c in enumerate(concepts, 1):
        lines.append(f"## {idx}. {c['name']} / {c['concept_id']}")
        lines.append("")

        lines.append("### 定义")
        lines.append("")
        lines.append(c["definition"])
        lines.append("")

        lines.append("### 来源 quote_ids")
        lines.append("")
        sqids = c.get("source_quote_ids", [])
        if sqids:
            for qid in sqids:
                lines.append(f"- `{qid}`")
        else:
            lines.append("（无）")
        lines.append("")

        lines.append("### 正向关键词")
        lines.append("")
        pk = c.get("positive_keywords", {})
        if pk:
            for group, words in pk.items():
                lines.append(f"- **{group}**: {', '.join(words)}")
        else:
            lines.append("（无）")
        lines.append("")

        lines.append("### 反向关键词")
        lines.append("")
        nk = c.get("negative_keywords", {})
        if nk:
            for group, words in nk.items():
                lines.append(f"- **{group}**: {', '.join(words)}")
        else:
            lines.append("（无）")
        lines.append("")

        lines.append("### 硬指标")
        lines.append("")
        for m in c.get("hard_metrics", []):
            lines.append(f"- `{m}`")
        lines.append("")

        lines.append("### 人工审核项")
        lines.append("")
        mr = c.get("manual_review", {})
        if mr.get("reason"):
            lines.append(f"审核原因：{mr['reason']}")
            lines.append("")
        lines.append("- [ ] 接受")
        lines.append("- [ ] 修改")
        lines.append("- [ ] 删除")
        lines.append("")

    content = "\n".join(lines)
    try:
        output_file.write_text(content, encoding="utf-8")
    except Exception as e:
        raise JsonlWriteError(f"Failed to write review to {output_file}: {e}") from e
