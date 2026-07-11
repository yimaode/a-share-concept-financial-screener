import json
from pathlib import Path

from .concept_validator import _can_freeze, validate_concepts_draft
from .concept_draft_writer import write_concepts_draft_json, write_concepts_draft_yaml
from .errors import ConceptBuilderError


class ConceptFreezeError(ConceptBuilderError):
    pass


def run_freeze_concepts(
    input_file: Path,
    output_json: Path,
    output_yaml: Path,
) -> None:
    if not input_file.exists():
        raise ConceptFreezeError(f"Concepts file not found: {input_file}")

    try:
        concepts_data = json.loads(input_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConceptFreezeError(f"Invalid JSON in {input_file}: {e}") from e

    issues = validate_concepts_draft(concepts_data)
    if issues:
        issue_lines = "\n".join(
            f"  - [{i['scope']}] {i['concept_id']}: {i['message']}"
            for i in issues
        )
        raise ConceptFreezeError(
            f"Freeze failed: {len(issues)} validation issue(s) found:\n{issue_lines}"
        )

    concepts = concepts_data.get("concepts", [])
    can_freeze, blockers = _can_freeze(concepts)
    if not can_freeze:
        blocker_lines = "\n".join(f"  - {b}" for b in blockers)
        raise ConceptFreezeError(
            f"Freeze failed: not all concepts are approved:\n{blocker_lines}"
        )

    for concept in concepts:
        concept["status"] = "frozen"

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_yaml.parent.mkdir(parents=True, exist_ok=True)

    frozen_data = {
        "version": concepts_data.get("version", "0.1.0"),
        "market": concepts_data.get("market", "A-share"),
        "strategy_focus": concepts_data.get("strategy_focus", "super_growth"),
        "language": concepts_data.get("language", "zh-CN"),
        "status": "frozen",
        "generated_from": str(input_file),
        "concepts": concepts,
    }

    try:
        with output_json.open("w", encoding="utf-8") as f:
            json.dump(frozen_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _cleanup_partial(output_json, output_yaml)
        raise ConceptFreezeError(f"Failed to write {output_json}: {e}") from e

    try:
        write_concepts_draft_yaml(concepts, output_yaml, str(input_file))
    except Exception as e:
        _cleanup_partial(output_json, output_yaml)
        raise ConceptFreezeError(f"Failed to write {output_yaml}: {e}") from e


def _cleanup_partial(json_path: Path, yaml_path: Path) -> None:
    for p in (json_path, yaml_path):
        if p.exists():
            p.unlink()
