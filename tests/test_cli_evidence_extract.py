import csv
import json
from pathlib import Path

from ds_finance_concept.cli import main


def _write_frozen_concepts(path: Path, concepts: list[dict]) -> None:
    path.write_text(json.dumps({
        "version": "0.1.0",
        "status": "frozen",
        "concepts": concepts,
    }, ensure_ascii=False), encoding="utf-8")


def _write_pages(path: Path, pages: list[dict]) -> None:
    lines = [json.dumps(p, ensure_ascii=False) for p in pages]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_manifest(path: Path, entries: list[dict]) -> None:
    lines = [json.dumps(e, ensure_ascii=False) for e in entries]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_cli_extract_evidence_normal(tmp_path):
    concepts_file = tmp_path / "concepts.json"
    _write_frozen_concepts(concepts_file, [
        {
            "concept_id": "sg",
            "name": "超级成长股",
            "positive_keywords": {"g": ["成长"]},
            "negative_keywords": {},
            "evidence_rules": {},
        }
    ])

    pages_file = tmp_path / "pages.jsonl"
    _write_pages(pages_file, [
        {
            "pdf_id": "pdf_1",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": "公司成长性良好。",
            "char_count": 8,
        }
    ])

    manifest_file = tmp_path / "manifest.jsonl"
    _write_manifest(manifest_file, [{"pdf_id": "pdf_1", "page_count": 1}])

    out_dir = tmp_path / "evidence"
    result = main([
        "extract-evidence",
        "--concepts-file", str(concepts_file),
        "--pages-file", str(pages_file),
        "--manifest-file", str(manifest_file),
        "--output-dir", str(out_dir),
    ])
    assert result == 0

    hits_file = out_dir / "evidence_hits.jsonl"
    assert hits_file.exists()
    hits = [json.loads(l) for l in hits_file.read_text(encoding="utf-8").strip().split("\n")]
    assert len(hits) >= 1
    assert hits[0]["evidence_id"].startswith("ev_")

    csv_file = out_dir / "evidence_hits.csv"
    assert csv_file.exists()
    with csv_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) >= 1
        assert rows[0]["concept_id"] == "sg"

    stats_file = out_dir / "concept_keyword_stats.json"
    assert stats_file.exists()
    stats = json.loads(stats_file.read_text(encoding="utf-8"))
    assert stats["total_hits"] >= 1

    report_file = out_dir / "evidence_report.md"
    assert report_file.exists()
    report = report_file.read_text(encoding="utf-8")
    assert "证据抽取报告" in report


def test_cli_non_frozen_fails(tmp_path):
    concepts_file = tmp_path / "concepts.json"
    concepts_file.write_text(json.dumps({
        "version": "0.1.0",
        "status": "draft",
        "concepts": [],
    }, ensure_ascii=False), encoding="utf-8")

    pages_file = tmp_path / "pages.jsonl"
    pages_file.write_text("", encoding="utf-8")

    manifest_file = tmp_path / "manifest.jsonl"
    manifest_file.write_text("", encoding="utf-8")

    result = main([
        "extract-evidence",
        "--concepts-file", str(concepts_file),
        "--pages-file", str(pages_file),
        "--manifest-file", str(manifest_file),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result != 0


def test_cli_bad_json_line_fails(tmp_path):
    concepts_file = tmp_path / "concepts.json"
    _write_frozen_concepts(concepts_file, [
        {
            "concept_id": "sg",
            "name": "超级成长股",
            "positive_keywords": {"g": ["成长"]},
            "negative_keywords": {},
            "evidence_rules": {},
        }
    ])

    pages_file = tmp_path / "pages.jsonl"
    pages_file.write_text("not json\n", encoding="utf-8")

    manifest_file = tmp_path / "manifest.jsonl"
    manifest_file.write_text("", encoding="utf-8")

    result = main([
        "extract-evidence",
        "--concepts-file", str(concepts_file),
        "--pages-file", str(pages_file),
        "--manifest-file", str(manifest_file),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result != 0


def test_cli_empty_output(tmp_path):
    concepts_file = tmp_path / "concepts.json"
    _write_frozen_concepts(concepts_file, [
        {
            "concept_id": "sg",
            "name": "超级成长股",
            "positive_keywords": {},
            "negative_keywords": {},
            "evidence_rules": {},
        }
    ])

    pages_file = tmp_path / "pages.jsonl"
    _write_pages(pages_file, [])

    manifest_file = tmp_path / "manifest.jsonl"
    _write_manifest(manifest_file, [])

    out_dir = tmp_path / "evidence"
    result = main([
        "extract-evidence",
        "--concepts-file", str(concepts_file),
        "--pages-file", str(pages_file),
        "--manifest-file", str(manifest_file),
        "--output-dir", str(out_dir),
    ])
    assert result == 0

    hits_file = out_dir / "evidence_hits.jsonl"
    assert hits_file.exists()

    csv_file = out_dir / "evidence_hits.csv"
    content = csv_file.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    assert len(lines) == 1
    assert "evidence_id" in lines[0]

    stats = json.loads((out_dir / "concept_keyword_stats.json").read_text(encoding="utf-8"))
    assert stats["total_hits"] == 0


def test_cli_manifest_warning(tmp_path):
    concepts_file = tmp_path / "concepts.json"
    _write_frozen_concepts(concepts_file, [
        {
            "concept_id": "sg",
            "name": "超级成长股",
            "positive_keywords": {"g": ["成长"]},
            "negative_keywords": {},
            "evidence_rules": {},
        }
    ])

    pages_file = tmp_path / "pages.jsonl"
    _write_pages(pages_file, [
        {
            "pdf_id": "pdf_missing",
            "source_pdf": "r.pdf",
            "relative_path": "r.pdf",
            "page_number": 1,
            "text": "公司成长性良好。",
            "char_count": 8,
        }
    ])

    manifest_file = tmp_path / "manifest.jsonl"
    _write_manifest(manifest_file, [{"pdf_id": "pdf_known", "page_count": 1}])

    out_dir = tmp_path / "evidence"
    result = main([
        "extract-evidence",
        "--concepts-file", str(concepts_file),
        "--pages-file", str(pages_file),
        "--manifest-file", str(manifest_file),
        "--output-dir", str(out_dir),
    ])
    assert result == 0

    report = (out_dir / "evidence_report.md").read_text(encoding="utf-8")
    assert "Warnings" in report or "warning" in report.lower()


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
