import json

from ds_finance_concept.cli import main


def test_prepare_concepts_creates_reviewable_workspace(tmp_path):
    notes = tmp_path / "private-notes"
    notes.mkdir()
    (notes / "example.md").write_text(
        "# 合成示例\n\n公司收入增长，订单储备充足，同时需要关注需求下滑风险。\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "private-workspace"

    assert main([
        "prepare-concepts", "--input-dir", str(notes),
        "--workspace-dir", str(workspace),
    ]) == 0

    expected = {
        "01_quote_cards.jsonl", "02_insight_cards.jsonl",
        "03_concept_candidates.json", "03_concept_candidates_review.md",
        "04_concepts.draft.json", "04_concepts.draft.yaml",
        "04_concepts_review.md",
    }
    assert expected <= {path.name for path in workspace.iterdir()}
    draft = json.loads((workspace / "04_concepts.draft.json").read_text(encoding="utf-8"))
    assert draft["status"] == "draft"


def test_screen_company_alias_dispatches_pipeline(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        "ds_finance_concept.cli.run_company_pipeline",
        lambda *args: calls.append(args) or 0,
    )
    assert main([
        "screen-company", "--company-code", "300750",
        "--concepts-file", str(tmp_path / "concepts.json"),
        "--output-dir", str(tmp_path / "out"),
    ]) == 0
    assert calls and calls[0][0] == "300750"
