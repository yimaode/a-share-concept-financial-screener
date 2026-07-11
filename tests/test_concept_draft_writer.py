from pathlib import Path

from ds_finance_concept.concept_builder.concept_draft_builder import build_draft_concepts
from ds_finance_concept.concept_builder.concept_draft_writer import (
    write_concept_review_md,
    write_concepts_draft_yaml,
)


def test_yaml_no_python_tags(tmp_path):
    draft = build_draft_concepts([])
    output = tmp_path / "concepts.yaml"
    write_concepts_draft_yaml(draft, output, "test.json")
    content = output.read_text(encoding="utf-8")
    assert "!!python" not in content
    assert "version:" in content
    assert "concepts:" in content


def test_empty_candidates_yaml_has_6_concepts(tmp_path):
    draft = build_draft_concepts([])
    output = tmp_path / "concepts.yaml"
    write_concepts_draft_yaml(draft, output, "test.json")
    content = output.read_text(encoding="utf-8")
    assert content.count("concept_id:") == 6


def test_yaml_contains_all_required_fields(tmp_path):
    draft = build_draft_concepts([])
    output = tmp_path / "concepts.yaml"
    write_concepts_draft_yaml(draft, output, "test.json")
    content = output.read_text(encoding="utf-8")
    assert "version:" in content
    assert "market:" in content
    assert "strategy_focus:" in content
    assert "status:" in content
    assert "generated_from:" in content
    assert "definition:" in content
    assert "positive_keywords:" in content
    assert "negative_keywords:" in content
    assert "hard_metrics:" in content
    assert "evidence_rules:" in content
    assert "scoring:" in content
    assert "manual_review:" in content


def test_yaml_stable_output(tmp_path):
    draft = build_draft_concepts([])
    output1 = tmp_path / "c1.yaml"
    output2 = tmp_path / "c2.yaml"
    write_concepts_draft_yaml(draft, output1, "test.json")
    write_concepts_draft_yaml(draft, output2, "test.json")
    assert output1.read_text() == output2.read_text()


def test_review_md_has_overview_table(tmp_path):
    draft = build_draft_concepts([])
    output = tmp_path / "review.md"
    write_concept_review_md(draft, output)
    content = output.read_text(encoding="utf-8")
    assert "# 概念草案审核报告" in content
    assert "## 总览" in content
    assert "concept_id" in content


def test_review_md_has_6_concept_sections(tmp_path):
    draft = build_draft_concepts([])
    output = tmp_path / "review.md"
    write_concept_review_md(draft, output)
    content = output.read_text(encoding="utf-8")
    assert content.count("### 定义") == 6
    assert content.count("### 人工审核项") == 6
    assert content.count("- [ ] 接受") == 6


def test_review_md_shows_evidence_when_present(tmp_path):
    candidates = [
        {
            "candidate_concept_id": "super_growth_stock",
            "canonical_name": "超级成长股",
            "source_quote_ids": ["q1", "q2"],
            "source_insight_ids": ["i1", "i2"],
        },
    ]
    draft = build_draft_concepts(candidates)
    output = tmp_path / "review.md"
    write_concept_review_md(draft, output)
    content = output.read_text(encoding="utf-8")
    assert "`q1`" in content
    assert "`q2`" in content


def test_creates_output_directory(tmp_path):
    draft = build_draft_concepts([])
    yaml_out = tmp_path / "deep" / "nested" / "c.yaml"
    md_out = tmp_path / "deep" / "nested" / "r.md"
    write_concepts_draft_yaml(draft, yaml_out, "test.json")
    write_concept_review_md(draft, md_out)
    assert yaml_out.exists()
    assert md_out.exists()
