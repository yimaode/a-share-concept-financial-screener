import json
from pathlib import Path

import pytest

from ds_finance_concept.concept_builder.concept_freezer import (
    ConceptFreezeError,
    run_freeze_concepts,
)


def test_freeze_fails_with_validation_errors(tmp_path):
    input_file = tmp_path / "draft.json"
    input_file.write_text(json.dumps({
        "version": "0.1.0",
        "concepts": [
            {"concept_id": "dup", "name": "A"},
            {"concept_id": "dup", "name": "B"},
        ],
    }, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ConceptFreezeError):
        run_freeze_concepts(input_file, tmp_path / "c.json", tmp_path / "c.yaml")

    assert not (tmp_path / "c.json").exists()
    assert not (tmp_path / "c.yaml").exists()


def test_freeze_fails_with_pending_review(tmp_path):
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
                "manual_review": {
                    "required": True,
                    "status": "pending",
                },
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ConceptFreezeError):
        run_freeze_concepts(input_file, tmp_path / "c.json", tmp_path / "c.yaml")

    assert not (tmp_path / "c.json").exists()


def test_freeze_succeeds_with_approved(tmp_path):
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
                "manual_review": {
                    "required": False,
                    "status": "approved",
                },
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    out_json = tmp_path / "c.json"
    out_yaml = tmp_path / "c.yaml"
    run_freeze_concepts(input_file, out_json, out_yaml)

    assert out_json.exists()
    assert out_yaml.exists()

    frozen = json.loads(out_json.read_text(encoding="utf-8"))
    assert frozen["status"] == "frozen"
    assert frozen["concepts"][0]["status"] == "frozen"


def test_freeze_with_needs_review_status_fails(tmp_path):
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
                "manual_review": {
                    "required": False,
                    "status": "needs_review",
                },
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ConceptFreezeError):
        run_freeze_concepts(input_file, tmp_path / "c.json", tmp_path / "c.yaml")


def test_freeze_with_approved_fixture(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "concepts.approved.json"
    out_json = tmp_path / "c.json"
    out_yaml = tmp_path / "c.yaml"
    run_freeze_concepts(fixture, out_json, out_yaml)
    assert out_json.exists()
    assert out_yaml.exists()


def test_freeze_fails_with_needs_review_fixture(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "concepts.needs_review.json"
    with pytest.raises(ConceptFreezeError):
        run_freeze_concepts(fixture, tmp_path / "c.json", tmp_path / "c.yaml")
