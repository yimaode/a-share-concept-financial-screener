import json
from pathlib import Path

from ds_finance_concept.concept_builder.concept_validator import (
    run_validate_concepts,
    validate_concepts_draft,
)


def test_valid_draft_passes():
    data = {
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
                "definition": "A test concept",
                "aliases": [],
                "source_quote_ids": [],
                "positive_keywords": {"g": ["k"]},
                "negative_keywords": {},
                "hard_metrics": [],
                "evidence_rules": {},
                "scoring": {},
                "manual_review": {"required": False, "status": "approved"},
            }
        ],
    }
    issues = validate_concepts_draft(data)
    assert len(issues) == 0


def test_missing_top_level_field():
    data = {
        "version": "0.1.0",
        "concepts": [],
    }
    issues = validate_concepts_draft(data)
    missing = [i for i in issues if i["scope"] == "top_level"]
    assert len(missing) > 0


def test_duplicate_concept_id():
    data = {
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
    }
    issues = validate_concepts_draft(data)
    dup_issues = [i for i in issues if i["message"].startswith("Duplicate")]
    assert len(dup_issues) == 1


def test_missing_definition():
    data = {
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
                "hard_metrics": [],
                "evidence_rules": {},
                "scoring": {},
                "manual_review": {"required": False, "status": "approved"},
            }
        ],
    }
    issues = validate_concepts_draft(data)
    def_issues = [i for i in issues if i["field"] == "definition"]
    assert len(def_issues) == 1


def test_missing_manual_review():
    data = {
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
                "definition": "x",
                "aliases": [],
                "source_quote_ids": [],
                "positive_keywords": {"g": ["k"]},
                "negative_keywords": {},
                "hard_metrics": [],
                "evidence_rules": {},
                "scoring": {},
            }
        ],
    }
    issues = validate_concepts_draft(data)
    mr_issues = [i for i in issues if "manual_review" in i["field"]]
    assert len(mr_issues) > 0


def test_no_keywords_fails():
    data = {
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
                "definition": "x",
                "aliases": [],
                "source_quote_ids": [],
                "positive_keywords": {},
                "negative_keywords": {},
                "hard_metrics": [],
                "evidence_rules": {},
                "scoring": {},
                "manual_review": {"required": False, "status": "approved"},
            }
        ],
    }
    issues = validate_concepts_draft(data)
    kw_issues = [i for i in issues if i["field"] == "keywords"]
    assert len(kw_issues) == 1


def test_validate_concepts_file_not_exists(tmp_path):
    from ds_finance_concept.concept_builder.concept_validator import ConceptValidationError
    import pytest
    with pytest.raises(ConceptValidationError):
        run_validate_concepts(tmp_path / "nope.json", tmp_path / "r.md")


def test_valid_file_generates_pass_report(tmp_path):
    input_file = tmp_path / "draft.json"
    input_file.write_text(json.dumps({
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
    passed, _ = run_validate_concepts(input_file, report)
    assert passed
    content = report.read_text(encoding="utf-8")
    assert "PASS" in content
