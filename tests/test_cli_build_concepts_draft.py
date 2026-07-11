import json
from pathlib import Path

from ds_finance_concept.cli import main


def test_cli_empty_candidates_generates_6(tmp_path):
    candidates_file = tmp_path / "candidates.json"
    candidates_file.write_text(json.dumps({
        "version": "0.1.0",
        "source_file": "test.jsonl",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    yaml_out = tmp_path / "draft.yaml"
    md_out = tmp_path / "review.md"

    result = main([
        "build-concepts-draft",
        "--candidates-file", str(candidates_file),
        "--output-yaml", str(yaml_out),
        "--output-review", str(md_out),
    ])
    assert result == 0
    yaml_content = yaml_out.read_text(encoding="utf-8")
    assert yaml_content.count("concept_id:") == 6


def test_cli_with_matching_candidates(tmp_path):
    candidates_file = tmp_path / "candidates.json"
    candidates_file.write_text(json.dumps({
        "version": "0.1.0",
        "source_file": "test.jsonl",
        "concepts": [
            {
                "candidate_concept_id": "super_growth_stock",
                "canonical_name": "超级成长股",
                "source_quote_ids": ["q1", "q2"],
                "source_insight_ids": ["i1", "i2"],
            },
        ],
    }, ensure_ascii=False), encoding="utf-8")

    yaml_out = tmp_path / "draft.yaml"
    md_out = tmp_path / "review.md"

    result = main([
        "build-concepts-draft",
        "--candidates-file", str(candidates_file),
        "--output-yaml", str(yaml_out),
        "--output-review", str(md_out),
    ])
    assert result == 0
    yaml_content = yaml_out.read_text(encoding="utf-8")
    assert "q1" in yaml_content


def test_cli_file_not_exists(tmp_path):
    result = main([
        "build-concepts-draft",
        "--candidates-file", str(tmp_path / "nonexistent.json"),
        "--output-yaml", str(tmp_path / "draft.yaml"),
        "--output-review", str(tmp_path / "review.md"),
    ])
    assert result != 0


def test_cli_yaml_no_python_tags(tmp_path):
    candidates_file = tmp_path / "candidates.json"
    candidates_file.write_text(json.dumps({
        "version": "0.1.0",
        "source_file": "test.jsonl",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    yaml_out = tmp_path / "draft.yaml"
    md_out = tmp_path / "review.md"

    result = main([
        "build-concepts-draft",
        "--candidates-file", str(candidates_file),
        "--output-yaml", str(yaml_out),
        "--output-review", str(md_out),
    ])
    assert result == 0
    assert "!!python" not in yaml_out.read_text(encoding="utf-8")


def test_build_quotes_still_works(tmp_path):
    md = tmp_path / "notes"
    md.mkdir()
    (md / "001.md").write_text("# H1\n\nText here long\n", encoding="utf-8")
    output = tmp_path / "quotes.jsonl"
    result = main([
        "build-quotes",
        "--input-dir", str(md),
        "--output-file", str(output),
    ])
    assert result == 0


def test_build_insights_still_works(tmp_path):
    quote_file = tmp_path / "quotes.jsonl"
    quote_file.write_text(
        json.dumps({
            "quote_id": "quote_abc",
            "source_file": "001.md",
            "heading_path": [],
            "raw_text": "公司成长性良好收入增长",
            "normalized_text": "公司成长性良好收入增长",
            "char_count": 12,
            "line_start": 1,
            "line_end": 1,
            "block_type": "paragraph",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "insights.jsonl"
    result = main([
        "build-insights",
        "--quote-file", str(quote_file),
        "--output-file", str(output),
    ])
    assert result == 0


def test_build_concept_candidates_still_works(tmp_path):
    insight_file = tmp_path / "insights.jsonl"
    insight_file.write_text(
        json.dumps({
            "insight_id": "i1",
            "quote_id": "q1",
            "source_file": "f.md",
            "heading_path": [],
            "original_text": "公司成长性良好",
            "investment_claim": "公司成长性良好",
            "candidate_concepts": ["超级成长股"],
            "observable_signals": [],
            "possible_financial_metrics": [],
            "possible_report_keywords": [],
            "not_quantifiable_parts": [],
            "confidence": "low",
            "extraction_method": "rule_based_v1",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    json_out = tmp_path / "concepts.json"
    md_out = tmp_path / "review.md"
    result = main([
        "build-concept-candidates",
        "--insight-file", str(insight_file),
        "--output-json", str(json_out),
        "--output-review", str(md_out),
    ])
    assert result == 0
