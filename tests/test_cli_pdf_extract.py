import json
from pathlib import Path

import fitz

from ds_finance_concept.cli import main


def make_pdf(path: Path, texts: list[str]) -> None:
    doc = fitz.open()
    for t in texts:
        page = doc.new_page()
        page.insert_text(fitz.Point(50, 100), t)
    doc.save(str(path))
    doc.close()


def test_cli_single_pdf(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    make_pdf(pdf_dir / "report.pdf", ["Hello World"])

    out_dir = tmp_path / "output"
    result = main([
        "extract-pdf-text",
        "--pdf-dir", str(pdf_dir),
        "--output-dir", str(out_dir),
    ])
    assert result == 0

    manifest_file = out_dir / "pdf_manifest.jsonl"
    pages_file = out_dir / "pages.jsonl"
    report_file = out_dir / "extraction_report.md"
    full_text_dir = out_dir / "full_text"

    assert manifest_file.exists()
    assert pages_file.exists()
    assert report_file.exists()
    assert full_text_dir.exists()

    manifest_lines = manifest_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(manifest_lines) == 1
    m = json.loads(manifest_lines[0])
    assert m["extract_status"] == "success"
    assert m["source_pdf"] == "report.pdf"

    pages_lines = pages_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(pages_lines) == 1
    p = json.loads(pages_lines[0])
    assert p["page_number"] == 1
    assert "Hello" in p["text"]

    txt_files = list(full_text_dir.glob("*.txt"))
    assert len(txt_files) == 1
    txt = txt_files[0].read_text(encoding="utf-8")
    assert "===== PAGE 1 =====" in txt
    assert "Hello World" in txt


def test_cli_empty_directory(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "output"
    result = main([
        "extract-pdf-text",
        "--pdf-dir", str(pdf_dir),
        "--output-dir", str(out_dir),
    ])
    assert result == 0
    assert (out_dir / "pdf_manifest.jsonl").exists()
    content = (out_dir / "extraction_report.md").read_text(encoding="utf-8")
    assert "PDF 总数 | 0" in content


def test_cli_non_pdf_ignored(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    make_pdf(pdf_dir / "r.pdf", ["Hello"])
    (pdf_dir / "notes.txt").write_text("ignored", encoding="utf-8")

    out_dir = tmp_path / "output"
    result = main([
        "extract-pdf-text",
        "--pdf-dir", str(pdf_dir),
        "--output-dir", str(out_dir),
    ])
    assert result == 0
    manifest = (out_dir / "pdf_manifest.jsonl").read_text(encoding="utf-8")
    assert manifest.count("\n") == 1


def test_cli_multi_page_pdf(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    make_pdf(pdf_dir / "multi.pdf", ["Page1", "Page2", "Page3"])

    out_dir = tmp_path / "output"
    result = main([
        "extract-pdf-text",
        "--pdf-dir", str(pdf_dir),
        "--output-dir", str(out_dir),
    ])
    assert result == 0

    pages = (out_dir / "pages.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(pages) == 3

    for i, line in enumerate(pages):
        p = json.loads(line)
        assert p["page_number"] == i + 1


def test_cli_corrupt_pdf_does_not_crash(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    make_pdf(pdf_dir / "good.pdf", ["Hello"])
    (pdf_dir / "bad.pdf").write_bytes(b"garbage")

    out_dir = tmp_path / "output"
    result = main([
        "extract-pdf-text",
        "--pdf-dir", str(pdf_dir),
        "--output-dir", str(out_dir),
    ])
    assert result == 0

    manifest = (out_dir / "pdf_manifest.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(manifest) == 2
    statuses = {json.loads(line)["extract_status"] for line in manifest}
    assert statuses == {"success", "failed"}

    report = (out_dir / "extraction_report.md").read_text(encoding="utf-8")
    assert "失败" in report


def test_cli_needs_ocr_flag(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_dir / "empty.pdf"))
    doc.close()

    out_dir = tmp_path / "output"
    result = main([
        "extract-pdf-text",
        "--pdf-dir", str(pdf_dir),
        "--output-dir", str(out_dir),
    ])
    assert result == 0

    manifest = json.loads(
        (out_dir / "pdf_manifest.jsonl").read_text(encoding="utf-8").strip()
    )
    assert manifest["needs_ocr"] is True

    report = (out_dir / "extraction_report.md").read_text(encoding="utf-8")
    assert "需要 OCR" in report


def test_cli_full_text_page_separator(tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    make_pdf(pdf_dir / "r.pdf", ["First page", "Second page"])

    out_dir = tmp_path / "output"
    result = main([
        "extract-pdf-text",
        "--pdf-dir", str(pdf_dir),
        "--output-dir", str(out_dir),
    ])
    assert result == 0

    txt = (out_dir / "full_text").glob("*.txt")
    content = list(txt)[0].read_text(encoding="utf-8")
    assert "===== PAGE 1 =====" in content
    assert "===== PAGE 2 =====" in content
    assert "First page" in content
    assert "Second page" in content


def test_cli_dir_not_exists(tmp_path):
    result = main([
        "extract-pdf-text",
        "--pdf-dir", str(tmp_path / "nope"),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result != 0


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
