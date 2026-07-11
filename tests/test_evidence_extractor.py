import json
from pathlib import Path

import pytest

from ds_finance_concept.evidence_extractor.errors import ConceptsNotFrozenError
from ds_finance_concept.evidence_extractor.extractor import (
    _build_keyword_index,
    _expand_keywords,
    _has_negation,
    _split_sentences,
    extract_evidence,
)


def test_split_chinese_sentences():
    text = "订单饱满。需求旺盛！产能释放了吗？是的。"
    sents = _split_sentences(text)
    assert len(sents) == 4
    assert sents[0] == "订单饱满。"
    assert "。" in sents[0]


def test_split_english_sentences():
    text = "Revenue grew 15%. Profit increased! Is demand strong? Yes."
    sents = _split_sentences(text)
    assert len(sents) == 4


def test_no_delimiter_returns_whole():
    text = "这是一段没有标点的文本"
    sents = _split_sentences(text)
    assert len(sents) == 1
    assert sents[0] == text


def test_expand_keywords_dict():
    data = {"growth": ["成长", "高增长"], "quality": ["龙头"]}
    pairs = _expand_keywords(data)
    assert ("growth", "成长") in pairs
    assert ("growth", "高增长") in pairs
    assert ("quality", "龙头") in pairs


def test_expand_keywords_list():
    data = ["需求旺盛", "订单饱满"]
    pairs = _expand_keywords(data)
    assert ("", "需求旺盛") in pairs
    assert ("", "订单饱满") in pairs


def test_has_negation_positive():
    assert _has_negation("业绩下滑明显") is True
    assert _has_negation("订单不足需要关注") is True
    assert _has_negation("毛利率下降") is True


def test_has_negation_no_negation():
    assert _has_negation("业绩持续增长") is False
    assert _has_negation("订单饱满需求旺盛") is False


def test_build_keyword_index():
    concepts = [
        {
            "concept_id": "c1",
            "name": "Test",
            "positive_keywords": {"g": ["成长"]},
            "negative_keywords": {"r": ["下滑"]},
        }
    ]
    idx = _build_keyword_index(concepts)
    assert len(idx) == 2
    pos = [e for e in idx if e["polarity"] == "positive"]
    neg = [e for e in idx if e["polarity"] == "negative"]
    assert len(pos) == 1
    assert len(neg) == 1


def test_non_frozen_concepts_fails(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "draft",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text("", encoding="utf-8")

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text("", encoding="utf-8")

    with pytest.raises(ConceptsNotFrozenError, match="frozen"):
        extract_evidence(concepts_file, pages_file, manifest_file)


def test_positive_keyword_hit(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {"g": ["成长"]},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_123",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": "公司成长性良好。订单饱满需求旺盛。",
            "char_count": 16,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_123", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    hits, warnings, _, stats = extract_evidence(concepts_file, pages_file, manifest_file)
    assert len(hits) >= 1
    assert hits[0].polarity == "positive"
    assert hits[0].keyword == "成长"
    assert hits[0].evidence_id.startswith("ev_")


def test_negative_keyword_hit(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "risk",
                "name": "风险",
                "positive_keywords": {},
                "negative_keywords": {"r": ["下滑"]},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": "业绩下滑明显。",
            "char_count": 6,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    hits, _, _, _ = extract_evidence(concepts_file, pages_file, manifest_file)
    assert len(hits) >= 1
    assert hits[0].polarity == "negative"
    assert hits[0].keyword == "下滑"


def test_boilerplate_risk_declaration_is_not_evidence(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0", "status": "frozen",
        "concepts": [{"concept_id": "risk", "name": "风险", "positive_keywords": {},
                      "negative_keywords": {"r": ["风险"]}}],
    }, ensure_ascii=False), encoding="utf-8")
    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(json.dumps({
        "pdf_id": "p", "source_pdf": "r.pdf", "relative_path": "r.pdf", "page_number": 1,
        "text": "前瞻性陈述的风险声明。公司可能面对的风险，敬请关注。", "char_count": 30,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(json.dumps({"pdf_id": "p"}) + "\n", encoding="utf-8")
    hits, _, _, _ = extract_evidence(concepts_file, pages_file, manifest_file)
    assert hits == []


def test_multi_keyword_same_sentence(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {"g": ["成长", "增长"]},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": "公司成长与增长并重。",
            "char_count": 10,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    hits, _, _, _ = extract_evidence(concepts_file, pages_file, manifest_file)
    keywords = {h.keyword for h in hits}
    assert "成长" in keywords
    assert "增长" in keywords


def test_dedup_same_hit(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {"g": ["成长"]},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    page = json.dumps({
        "pdf_id": "pdf_1",
        "source_pdf": "r.pdf",
        "relative_path": "r.pdf",
        "page_number": 1,
        "text": "公司成长性良好。公司成长性良好。",
        "char_count": 12,
    }, ensure_ascii=False)
    pages_file.write_text(page + "\n" + page + "\n", encoding="utf-8")

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    hits, _, _, _ = extract_evidence(concepts_file, pages_file, manifest_file)
    assert len(hits) == 1


def test_negation_detection(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {"g": ["成长"]},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": "公司成长不及预期。",
            "char_count": 9,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    hits, _, _, _ = extract_evidence(concepts_file, pages_file, manifest_file)
    assert len(hits) == 1
    assert hits[0].negation_detected is True


def test_long_sentence_truncated(tmp_path):
    long_text = "公司" + "成长" * 300
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {"g": ["成长"]},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": long_text,
            "char_count": len(long_text),
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    hits, _, _, _ = extract_evidence(concepts_file, pages_file, manifest_file)
    assert len(hits) >= 1
    assert hits[0].truncated is True
    assert len(hits[0].sentence) <= 500


def test_empty_pages_no_hits(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text("", encoding="utf-8")

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text("", encoding="utf-8")

    hits, _, _, stats = extract_evidence(concepts_file, pages_file, manifest_file)
    assert hits == []
    assert stats["total_hits"] == 0


def test_bad_json_line_raises(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {"g": ["成长"]},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text("not json\n", encoding="utf-8")

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text("", encoding="utf-8")

    with pytest.raises(Exception):
        extract_evidence(concepts_file, pages_file, manifest_file)


def test_manifest_warning(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {"g": ["成长"]},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_missing",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": "公司成长性良好。",
            "char_count": 8,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_known", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    hits, warnings, _, _ = extract_evidence(concepts_file, pages_file, manifest_file)
    assert len(hits) >= 1
    assert len(warnings) >= 1
    assert "pdf_missing" in warnings[0]


def test_context_before_after(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {"g": ["成长"]},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": "业绩表现良好。公司成长性突出。后续展望积极。",
            "char_count": 20,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    hits, _, _, _ = extract_evidence(concepts_file, pages_file, manifest_file)
    assert len(hits) >= 1
    assert "业绩表现良好" in hits[0].context_before
    assert "后续展望积极" in hits[0].context_after


def test_stats_total_hits(tmp_path):
    concepts_file = tmp_path / "c.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": [
            {
                "concept_id": "sg",
                "name": "超级成长股",
                "positive_keywords": {"g": ["成长", "增长"]},
                "negative_keywords": {},
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "p.jsonl"
    pages_file.write_text(
        json.dumps({
            "pdf_id": "pdf_1",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": "公司成长性良好，业绩增长快速。",
            "char_count": 14,
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    manifest_file = tmp_path / "m.jsonl"
    manifest_file.write_text(
        json.dumps({"pdf_id": "pdf_1", "page_count": 1}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _, _, _, stats = extract_evidence(concepts_file, pages_file, manifest_file)
    assert stats["total_hits"] >= 1
