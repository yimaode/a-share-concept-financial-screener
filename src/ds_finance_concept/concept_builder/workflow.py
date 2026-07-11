"""Stage-one workflow: private notes -> reviewable concept draft workspace."""

from __future__ import annotations

from pathlib import Path
import json

from .concept_candidate_builder import build_concept_candidates
from .concept_candidate_writer import (
    write_concept_candidates_json,
    write_concept_candidates_review_md,
)
from .concept_draft_builder import build_draft_concepts
from .concept_draft_writer import (
    write_concept_review_md,
    write_concepts_draft_json,
    write_concepts_draft_yaml,
)
from .insight_extractor import extract_insights_from_quotes
from .insight_writer import write_insight_cards_jsonl
from .jsonl_writer import write_quote_cards_jsonl
from .markdown_parser import parse_markdown_dir
from .quote_reader import read_quote_cards_jsonl


def prepare_concept_workspace(input_dir: Path, workspace_dir: Path) -> dict[str, int]:
    """Build deterministic, reviewable intermediates without freezing concepts.

    The workspace may contain private source text and should remain outside Git.
    Freezing is deliberately a separate, explicit command after human review.
    """
    input_dir = Path(input_dir)
    workspace_dir = Path(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    quotes = parse_markdown_dir(input_dir)
    quote_file = workspace_dir / "01_quote_cards.jsonl"
    write_quote_cards_jsonl(quotes, quote_file)

    insights = extract_insights_from_quotes(read_quote_cards_jsonl(quote_file))
    insight_file = workspace_dir / "02_insight_cards.jsonl"
    write_insight_cards_jsonl(insights, insight_file)

    candidate_inputs = read_quote_cards_jsonl(insight_file)
    candidates = build_concept_candidates(candidate_inputs)
    candidate_file = workspace_dir / "03_concept_candidates.json"
    write_concept_candidates_json(candidates, candidate_file, str(insight_file))
    write_concept_candidates_review_md(
        candidates, workspace_dir / "03_concept_candidates_review.md"
    )

    candidate_data = json.loads(candidate_file.read_text(encoding="utf-8"))
    drafts = build_draft_concepts(candidate_data.get("concepts", []))
    draft_json = workspace_dir / "04_concepts.draft.json"
    write_concepts_draft_json(drafts, draft_json, str(candidate_file))
    write_concepts_draft_yaml(
        drafts, workspace_dir / "04_concepts.draft.yaml", str(candidate_file)
    )
    write_concept_review_md(drafts, workspace_dir / "04_concepts_review.md")

    return {
        "quotes": len(quotes),
        "insights": len(insights),
        "candidates": len(candidates),
        "drafts": len(drafts),
    }
