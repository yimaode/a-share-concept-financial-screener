from copy import deepcopy

from .concept_templates import CANDIDATE_ID_TO_TEMPLATE_ID, CONCEPT_TEMPLATES


def build_draft_concepts(candidates: list[dict]) -> list[dict]:
    templates = deepcopy(CONCEPT_TEMPLATES)

    candidates_by_template: dict[str, list[dict]] = {}
    for c in candidates:
        cid = c.get("candidate_concept_id", "")
        template_id = CANDIDATE_ID_TO_TEMPLATE_ID.get(cid)
        if template_id:
            candidates_by_template.setdefault(template_id, []).append(c)

    for template in templates:
        tid = template["concept_id"]
        matched = candidates_by_template.get(tid, [])

        source_quote_ids: set[str] = set()
        for mc in matched:
            source_quote_ids.update(mc.get("source_quote_ids", []))

        template["source_quote_ids"] = sorted(source_quote_ids)
        template["evidence_count"] = len(source_quote_ids)

        mr_required = (
            template["evidence_count"]
            < template["evidence_rules"]["min_evidence_count"]
        )
        template["manual_review"] = {
            "required": mr_required,
            "status": "pending" if mr_required else "approved",
            "reason": (
                f"证据不足（{template['evidence_count']}条，最低要求{template['evidence_rules']['min_evidence_count']}条）"
                if mr_required
                else ""
            ),
            "evidence_count": template["evidence_count"],
            "notes": [],
        }

    return templates
