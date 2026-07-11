import json
from pathlib import Path

from ds_finance_concept.cli import main


def test_build_draft_outputs_json(tmp_path):
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
    json_out = tmp_path / "draft.json"
    md_out = tmp_path / "review.md"

    result = main([
        "build-concepts-draft",
        "--candidates-file", str(candidates_file),
        "--output-yaml", str(yaml_out),
        "--output-json", str(json_out),
        "--output-review", str(md_out),
    ])
    assert result == 0
    assert json_out.exists()

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["version"] == "0.1.0"
    assert "language" in data
    assert len(data["concepts"]) == 6
    for c in data["concepts"]:
        assert "manual_review" in c
        assert "status" in c["manual_review"]


def test_build_draft_json_matches_yaml_content(tmp_path):
    candidates_file = tmp_path / "candidates.json"
    candidates_file.write_text(json.dumps({
        "version": "0.1.0",
        "source_file": "test.jsonl",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    yaml_out = tmp_path / "draft.yaml"
    json_out = tmp_path / "draft.json"
    md_out = tmp_path / "review.md"

    result = main([
        "build-concepts-draft",
        "--candidates-file", str(candidates_file),
        "--output-yaml", str(yaml_out),
        "--output-json", str(json_out),
        "--output-review", str(md_out),
    ])
    assert result == 0

    data = json.loads(json_out.read_text(encoding="utf-8"))
    yaml_content = yaml_out.read_text(encoding="utf-8")

    assert data["concepts"][0]["concept_id"] in yaml_content


def test_validate_cli_pass(tmp_path):
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps({
        "version": "0.1.0",
        "market": "A-share",
        "strategy_focus": "super_growth",
        "language": "zh-CN",
        "status": "draft",
        "concepts": [
            {
                "concept_id": "c1",
                "name": "Test",
                "status": "draft",
                "definition": "A test",
                "aliases": [],
                "source_quote_ids": [],
                "positive_keywords": {"g": ["k"]},
                "negative_keywords": {},
                "hard_metrics": ["m"],
                "evidence_rules": {},
                "scoring": {},
                "manual_review": {"required": False, "status": "approved"},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    report = tmp_path / "report.md"
    result = main([
        "validate-concepts",
        "--concepts-json", str(draft_file),
        "--output-report", str(report),
    ])
    assert result == 0


def test_validate_cli_fail_missing_definition(tmp_path):
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps({
        "version": "0.1.0",
        "market": "A-share",
        "strategy_focus": "super_growth",
        "language": "zh-CN",
        "status": "draft",
        "concepts": [
            {
                "concept_id": "c1",
                "name": "Test",
                "status": "draft",
                "definition": "",
                "aliases": [],
                "source_quote_ids": [],
                "positive_keywords": {"g": ["k"]},
                "negative_keywords": {},
                "hard_metrics": ["m"],
                "evidence_rules": {},
                "scoring": {},
                "manual_review": {"required": False, "status": "approved"},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    report = tmp_path / "report.md"
    result = main([
        "validate-concepts",
        "--concepts-json", str(draft_file),
        "--output-report", str(report),
    ])
    assert result != 0
    content = report.read_text(encoding="utf-8")
    assert "FAIL" in content


def test_validate_cli_duplicate_ids(tmp_path):
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps({
        "version": "0.1.0",
        "market": "A-share",
        "strategy_focus": "super_growth",
        "language": "zh-CN",
        "status": "draft",
        "concepts": [
            {
                "concept_id": "dup",
                "name": "A",
                "status": "draft",
                "definition": "x",
                "aliases": [],
                "source_quote_ids": [],
                "positive_keywords": {"g": ["k"]},
                "negative_keywords": {},
                "hard_metrics": [],
                "evidence_rules": {},
                "scoring": {},
                "manual_review": {"required": False, "status": "approved"},
            },
            {
                "concept_id": "dup",
                "name": "B",
                "status": "draft",
                "definition": "x",
                "aliases": [],
                "source_quote_ids": [],
                "positive_keywords": {"g": ["k"]},
                "negative_keywords": {},
                "hard_metrics": [],
                "evidence_rules": {},
                "scoring": {},
                "manual_review": {"required": False, "status": "approved"},
            },
        ],
    }, ensure_ascii=False), encoding="utf-8")

    report = tmp_path / "report.md"
    result = main([
        "validate-concepts",
        "--concepts-json", str(draft_file),
        "--output-report", str(report),
    ])
    assert result != 0


def test_validate_reports_cannot_freeze_when_pending(tmp_path):
    draft_file = tmp_path / "draft.json"
    draft_file.write_text(json.dumps({
        "version": "0.1.0",
        "market": "A-share",
        "strategy_focus": "super_growth",
        "language": "zh-CN",
        "status": "draft",
        "concepts": [
            {
                "concept_id": "c1",
                "name": "Test",
                "status": "draft",
                "definition": "A test",
                "aliases": [],
                "source_quote_ids": [],
                "positive_keywords": {"g": ["k"]},
                "negative_keywords": {},
                "hard_metrics": ["m"],
                "evidence_rules": {},
                "scoring": {},
                "manual_review": {
                    "required": True,
                    "status": "pending",
                },
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    report = tmp_path / "report.md"
    result = main([
        "validate-concepts",
        "--concepts-json", str(draft_file),
        "--output-report", str(report),
    ])
    assert result == 0
    content = report.read_text(encoding="utf-8")
    assert "不允许冻结" in content


def test_freeze_cli_fails_with_needs_review(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "concepts.needs_review.json"
    result = main([
        "freeze-concepts",
        "--concepts-json", str(fixture),
        "--output-json", str(tmp_path / "c.json"),
        "--output-yaml", str(tmp_path / "c.yaml"),
    ])
    assert result != 0
    assert not (tmp_path / "c.json").exists()
    assert not (tmp_path / "c.yaml").exists()


def test_freeze_cli_succeeds_with_approved(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "concepts.approved.json"
    out_json = tmp_path / "c.json"
    out_yaml = tmp_path / "c.yaml"
    result = main([
        "freeze-concepts",
        "--concepts-json", str(fixture),
        "--output-json", str(out_json),
        "--output-yaml", str(out_yaml),
    ])
    assert result == 0
    assert out_json.exists()
    assert out_yaml.exists()
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["status"] == "frozen"


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
