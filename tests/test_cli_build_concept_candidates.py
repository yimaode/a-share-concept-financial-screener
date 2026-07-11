import json
from pathlib import Path

from ds_finance_concept.cli import main


def _write_insight_file(path: Path, insights: list[dict]) -> None:
    lines = []
    for ins in insights:
        lines.append(json.dumps(ins, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_insight_data(overrides=None):
    defaults = {
        "insight_id": "insight_001",
        "quote_id": "quote_001",
        "source_file": "001.md",
        "heading_path": ["H1"],
        "original_text": "公司成长性良好",
        "investment_claim": "公司成长性良好",
        "candidate_concepts": ["超级成长股"],
        "observable_signals": ["营业收入增长"],
        "possible_financial_metrics": ["revenue_yoy"],
        "possible_report_keywords": ["收入"],
        "not_quantifiable_parts": [],
        "confidence": "high",
        "extraction_method": "rule_based_v1",
    }
    if overrides:
        defaults.update(overrides)
    return defaults


def test_cli_generates_json_and_md(tmp_path):
    insight_file = tmp_path / "insights.jsonl"
    _write_insight_file(insight_file, [
        make_insight_data(),
        make_insight_data({
            "insight_id": "insight_002",
            "quote_id": "quote_002",
            "confidence": "medium",
        }),
    ])
    json_out = tmp_path / "concepts.json"
    md_out = tmp_path / "review.md"

    result = main([
        "build-concept-candidates",
        "--insight-file", str(insight_file),
        "--output-json", str(json_out),
        "--output-review", str(md_out),
    ])
    assert result == 0
    assert json_out.exists()
    assert md_out.exists()

    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["version"] == "0.1.0"
    assert "concepts" in data
    assert len(data["concepts"]) == 1
    assert data["concepts"][0]["candidate_concept_id"] == "super_growth_stock"


def test_cli_empty_insight_file(tmp_path):
    insight_file = tmp_path / "insights.jsonl"
    insight_file.write_text("", encoding="utf-8")
    json_out = tmp_path / "concepts.json"
    md_out = tmp_path / "review.md"

    result = main([
        "build-concept-candidates",
        "--insight-file", str(insight_file),
        "--output-json", str(json_out),
        "--output-review", str(md_out),
    ])
    assert result == 0
    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["concepts"] == []


def test_cli_file_not_exists(tmp_path):
    json_out = tmp_path / "concepts.json"
    md_out = tmp_path / "review.md"

    result = main([
        "build-concept-candidates",
        "--insight-file", str(tmp_path / "nonexistent.jsonl"),
        "--output-json", str(json_out),
        "--output-review", str(md_out),
    ])
    assert result != 0


def test_cli_creates_output_dirs(tmp_path):
    insight_file = tmp_path / "insights.jsonl"
    _write_insight_file(insight_file, [make_insight_data()])
    json_out = tmp_path / "deep" / "nested" / "concepts.json"
    md_out = tmp_path / "deep" / "nested" / "review.md"

    result = main([
        "build-concept-candidates",
        "--insight-file", str(insight_file),
        "--output-json", str(json_out),
        "--output-review", str(md_out),
    ])
    assert result == 0
    assert json_out.exists()
    assert md_out.exists()


def test_cli_review_md_has_expected_sections(tmp_path):
    insight_file = tmp_path / "insights.jsonl"
    _write_insight_file(insight_file, [make_insight_data()])
    md_out = tmp_path / "review.md"

    result = main([
        "build-concept-candidates",
        "--insight-file", str(insight_file),
        "--output-json", str(json_out := str(tmp_path / "concepts.json")),
        "--output-review", str(md_out),
    ])
    assert result == 0
    content = md_out.read_text(encoding="utf-8")
    assert "# 候选概念审核报告" in content
    assert "## 概览" in content
    assert "## 候选概念：超级成长股" in content
    assert "### 定义草稿" in content
    assert "### 来源 Insight" in content
    assert "### 来源 Quote ID" in content
    assert "### 置信度统计" in content
    assert "### 人工审核项" in content
    assert "- [ ] 接受" in content
    assert "- [ ] 修改" in content
    assert "- [ ] 删除" in content


def test_build_quotes_still_works(tmp_path):
    md = tmp_path / "notes"
    md.mkdir()
    (md / "001.md").write_text("# H1\n\nText here longer\n", encoding="utf-8")
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
