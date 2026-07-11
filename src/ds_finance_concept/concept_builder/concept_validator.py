import json
from pathlib import Path
from datetime import datetime

from .errors import ConceptBuilderError

TOP_LEVEL_FIELDS = ["version", "market", "strategy_focus", "language", "status", "concepts"]
CONCEPT_REQUIRED_FIELDS = [
    "concept_id", "name", "status", "definition",
    "aliases", "source_quote_ids",
    "positive_keywords", "negative_keywords",
    "hard_metrics", "evidence_rules", "scoring", "manual_review",
]
MANUAL_REVIEW_REQUIRED_FIELDS = ["required", "status"]


class ConceptValidationError(ConceptBuilderError):
    pass


def validate_concepts_draft(concepts_data: dict) -> list[dict]:
    issues: list[dict] = []

    for field in TOP_LEVEL_FIELDS:
        if field not in concepts_data:
            issues.append({
                "scope": "top_level",
                "concept_id": "",
                "field": field,
                "message": f"Missing top-level field: {field}",
            })

    concepts = concepts_data.get("concepts", [])
    if not isinstance(concepts, list):
        issues.append({
            "scope": "top_level",
            "concept_id": "",
            "field": "concepts",
            "message": "concepts must be a list",
        })
        return issues

    seen_ids: set[str] = set()

    for idx, concept in enumerate(concepts):
        if not isinstance(concept, dict):
            issues.append({
                "scope": "concept",
                "concept_id": f"[index {idx}]",
                "field": "",
                "message": "Concept is not a dict",
            })
            continue

        cid = concept.get("concept_id", f"[index {idx}]")

        for field in CONCEPT_REQUIRED_FIELDS:
            if field not in concept:
                issues.append({
                    "scope": "concept",
                    "concept_id": cid,
                    "field": field,
                    "message": f"Missing required field: {field}",
                })

        if cid in seen_ids:
            issues.append({
                "scope": "concept",
                "concept_id": cid,
                "field": "concept_id",
                "message": f"Duplicate concept_id: {cid}",
            })
        seen_ids.add(cid)

        definition = concept.get("definition", "")
        if not definition:
            issues.append({
                "scope": "concept",
                "concept_id": cid,
                "field": "definition",
                "message": "definition must not be empty",
            })

        positive = concept.get("positive_keywords", {})
        negative = concept.get("negative_keywords", {})
        if not isinstance(positive, dict) or not isinstance(negative, dict):
            issues.append({
                "scope": "concept",
                "concept_id": cid,
                "field": "keywords",
                "message": "positive_keywords and negative_keywords must be dicts",
            })
        elif not positive and not negative:
            issues.append({
                "scope": "concept",
                "concept_id": cid,
                "field": "keywords",
                "message": "At least one of positive_keywords or negative_keywords must be non-empty",
            })

        hard_metrics = concept.get("hard_metrics", [])
        if not isinstance(hard_metrics, list):
            issues.append({
                "scope": "concept",
                "concept_id": cid,
                "field": "hard_metrics",
                "message": "hard_metrics must be a list",
            })

        evidence_rules = concept.get("evidence_rules", {})
        if not isinstance(evidence_rules, dict):
            issues.append({
                "scope": "concept",
                "concept_id": cid,
                "field": "evidence_rules",
                "message": "evidence_rules must be a dict",
            })

        scoring = concept.get("scoring", {})
        if not isinstance(scoring, dict):
            issues.append({
                "scope": "concept",
                "concept_id": cid,
                "field": "scoring",
                "message": "scoring must be a dict",
            })

        source_qids = concept.get("source_quote_ids", None)
        if not isinstance(source_qids, list):
            issues.append({
                "scope": "concept",
                "concept_id": cid,
                "field": "source_quote_ids",
                "message": "source_quote_ids must be a list",
            })

        mr = concept.get("manual_review", {})
        if not isinstance(mr, dict):
            issues.append({
                "scope": "concept",
                "concept_id": cid,
                "field": "manual_review",
                "message": "manual_review must be a dict",
            })
        else:
            for mrf in MANUAL_REVIEW_REQUIRED_FIELDS:
                if mrf not in mr:
                    issues.append({
                        "scope": "concept",
                        "concept_id": cid,
                        "field": f"manual_review.{mrf}",
                        "message": f"Missing manual_review field: {mrf}",
                    })

    return issues


def _can_freeze(concepts: list[dict]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    for concept in concepts:
        cid = concept.get("concept_id", "unknown")
        mr = concept.get("manual_review", {})
        required = mr.get("required", True)
        status = mr.get("status", "pending")

        if required and status != "approved":
            blockers.append(f"{cid}: manual_review.required=true and status={status!r}")
        elif status in ("pending", "draft", "needs_review"):
            blockers.append(f"{cid}: status={status!r} is not approved")

    return len(blockers) == 0, blockers


def _generate_validation_md(
    concepts_data: dict,
    issues: list[dict],
    concepts: list[dict],
) -> str:
    lines: list[str] = []
    lines.append("# 概念校验报告")
    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    total_concepts = len(concepts)
    has_issues = len(issues) > 0

    can_freeze, freeze_blockers = _can_freeze(concepts)

    lines.append("## 总体状态")
    lines.append("")
    if has_issues:
        lines.append("**FAIL** — 存在校验错误")
    else:
        lines.append("**PASS** — 所有校验通过")
    lines.append("")

    lines.append(f"- 概念数量: {total_concepts}")
    lines.append(f"- 校验错误数量: {len(issues)}")
    lines.append("")

    if has_issues:
        lines.append("## 校验错误详情")
        lines.append("")
        lines.append("| 范围 | concept_id | 字段 | 错误信息 |")
        lines.append("| --- | --- | --- | --- |")
        for issue in issues:
            lines.append(
                f"| {issue['scope']} | {issue['concept_id']} | "
                f"{issue['field']} | {issue['message']} |"
            )
        lines.append("")

    lines.append("## 概念校验状态")
    lines.append("")
    lines.append("| concept_id | 状态 | 审核状态 | 可冻结 |")
    lines.append("| --- | --- | --- | --- |")
    for concept in concepts:
        cid = concept.get("concept_id", "?")
        cstatus = concept.get("status", "draft")
        mr = concept.get("manual_review", {})
        mr_status = mr.get("status", "?")
        mr_required = mr.get("required", True)
        concept_issues = [i for i in issues if i.get("concept_id") == cid]
        frozen = "否" if concept_issues or (mr_required and mr_status != "approved") else "是"
        lines.append(f"| {cid} | {cstatus} | {mr_status} | {frozen} |")
    lines.append("")

    lines.append("## 需人工审核的概念")
    lines.append("")
    needs_review = [c for c in concepts if c.get("manual_review", {}).get("required", True)]
    if needs_review:
        for c in needs_review:
            mr = c.get("manual_review", {})
            lines.append(f"- **{c['concept_id']}** ({c.get('name', '')}): {mr.get('reason', '需要人工审核')}")
    else:
        lines.append("无")
    lines.append("")

    lines.append("## 冻结状态")
    lines.append("")
    if has_issues:
        lines.append("**不允许冻结** — 存在结构校验错误")
    elif can_freeze:
        lines.append("**允许冻结** — 所有概念通过校验且审核状态为 approved")
    else:
        lines.append("**不允许冻结** — 存在未通过审核的概念：")
        for blocker in freeze_blockers:
            lines.append(f"- {blocker}")
    lines.append("")

    return "\n".join(lines)


def run_validate_concepts(
    input_file: Path,
    output_report: Path,
) -> tuple[bool, str]:
    if not input_file.exists():
        raise ConceptValidationError(f"Concepts file not found: {input_file}")

    try:
        concepts_data = json.loads(input_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConceptValidationError(f"Invalid JSON in {input_file}: {e}") from e

    concepts = concepts_data.get("concepts", [])
    issues = validate_concepts_draft(concepts_data)
    report = _generate_validation_md(concepts_data, issues, concepts)

    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(report, encoding="utf-8")

    return len(issues) == 0, report
