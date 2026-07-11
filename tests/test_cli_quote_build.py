import json
from pathlib import Path

from ds_finance_concept.cli import main


def test_cli_input_dir_not_exists(tmp_path):
    result = main([
        "build-quotes",
        "--input-dir", str(tmp_path / "nonexistent"),
        "--output-file", str(tmp_path / "output.jsonl"),
    ])
    assert result != 0


def test_cli_input_path_not_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello", encoding="utf-8")
    result = main([
        "build-quotes",
        "--input-dir", str(f),
        "--output-file", str(tmp_path / "output.jsonl"),
    ])
    assert result != 0


def test_cli_empty_directory(tmp_path):
    d = tmp_path / "empty_dir"
    d.mkdir()
    output = tmp_path / "out.jsonl"
    result = main([
        "build-quotes",
        "--input-dir", str(d),
        "--output-file", str(output),
    ])
    assert result == 0
    assert output.exists()
    content = output.read_text(encoding="utf-8").strip()
    assert content == ""


def test_cli_generates_valid_jsonl(tmp_path):
    md = tmp_path / "notes"
    md.mkdir()
    (md / "001.md").write_text("# H1\n\nPara.\n", encoding="utf-8")
    output = tmp_path / "out.jsonl"

    result = main([
        "build-quotes",
        "--input-dir", str(md),
        "--output-file", str(output),
    ])
    assert result == 0
    assert output.exists()

    lines = output.read_text(encoding="utf-8").strip().split("\n")
    for line in lines:
        data = json.loads(line)
        assert "quote_id" in data
        assert "source_file" in data
        assert "heading_path" in data
        assert "block_type" in data
        assert "raw_text" in data
        assert "normalized_text" in data
        assert "char_count" in data
        assert "line_start" in data
        assert "line_end" in data
        assert data["char_count"] == len(data["normalized_text"])


def test_cli_creates_output_directory(tmp_path):
    md = tmp_path / "notes"
    md.mkdir()
    (md / "001.md").write_text("# Test\n", encoding="utf-8")

    output = tmp_path / "nested" / "dir" / "out.jsonl"

    result = main([
        "build-quotes",
        "--input-dir", str(md),
        "--output-file", str(output),
    ])
    assert result == 0
    assert output.exists()


def test_cli_multiple_md_files(tmp_path):
    md = tmp_path / "notes"
    md.mkdir()
    (md / "001.md").write_text("# A\n\nText A\n", encoding="utf-8")
    (md / "002.md").write_text("# B\n\nText B\n", encoding="utf-8")
    output = tmp_path / "out.jsonl"

    result = main([
        "build-quotes",
        "--input-dir", str(md),
        "--output-file", str(output),
    ])
    assert result == 0
    lines = output.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 4
