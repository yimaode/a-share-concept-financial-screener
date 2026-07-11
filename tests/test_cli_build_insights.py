import json
from pathlib import Path

from ds_finance_concept.cli import main


def test_build_insights_normal(tmp_path):
    quote_file = tmp_path / "quotes.jsonl"
    quote_file.write_text(
        json.dumps({
            "quote_id": "quote_abc",
            "source_file": "001.md",
            "heading_path": ["H1"],
            "raw_text": "公司成长性良好收入利润双增长",
            "normalized_text": "公司成长性良好收入利润双增长",
            "char_count": 14,
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
    assert output.exists()

    lines = output.read_text(encoding="utf-8").strip().split("\n")
    for line in lines:
        data = json.loads(line)
        assert "insight_id" in data
        assert "quote_id" in data
        assert data["quote_id"] == "quote_abc"
        assert data["extraction_method"] == "rule_based_v1"


def test_build_insights_empty_quote_file(tmp_path):
    quote_file = tmp_path / "quotes.jsonl"
    quote_file.write_text("", encoding="utf-8")

    output = tmp_path / "insights.jsonl"
    result = main([
        "build-insights",
        "--quote-file", str(quote_file),
        "--output-file", str(output),
    ])
    assert result == 0
    content = output.read_text(encoding="utf-8").strip()
    assert content == ""


def test_build_insights_file_not_exists(tmp_path):
    output = tmp_path / "insights.jsonl"
    result = main([
        "build-insights",
        "--quote-file", str(tmp_path / "nonexistent.jsonl"),
        "--output-file", str(output),
    ])
    assert result != 0


def test_build_insights_invalid_jsonl(tmp_path):
    quote_file = tmp_path / "quotes.jsonl"
    quote_file.write_text("not valid json\n", encoding="utf-8")

    output = tmp_path / "insights.jsonl"
    result = main([
        "build-insights",
        "--quote-file", str(quote_file),
        "--output-file", str(output),
    ])
    assert result != 0


def test_build_insights_creates_output_dir(tmp_path):
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

    output = tmp_path / "deep" / "nested" / "insights.jsonl"
    result = main([
        "build-insights",
        "--quote-file", str(quote_file),
        "--output-file", str(output),
    ])
    assert result == 0
    assert output.exists()


def test_build_quotes_still_works(tmp_path):
    md = tmp_path / "notes"
    md.mkdir()
    (md / "001.md").write_text("# H1\n\nText\n", encoding="utf-8")
    output = tmp_path / "quotes.jsonl"
    result = main([
        "build-quotes",
        "--input-dir", str(md),
        "--output-file", str(output),
    ])
    assert result == 0
    assert output.exists()
