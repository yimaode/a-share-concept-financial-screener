import json
from pathlib import Path

import fitz
import pytest

from ds_finance_concept.pdf_extractor.extractor import (
    extract_pdf_directory,
    extract_pdf_file,
)
from ds_finance_concept.pdf_extractor.manifest import (
    compute_sha256,
    generate_pdf_id,
    normalize_page_text,
)


@pytest.fixture
def single_page_pdf(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 100), "Hello World 测试文本")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def multi_page_pdf(tmp_path):
    pdf_path = tmp_path / "multi.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text(fitz.Point(50, 100), f"Page {i + 1} content here")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def empty_page_pdf(tmp_path):
    pdf_path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_single_page_pdf_extraction(single_page_pdf):
    manifest, pages = extract_pdf_file(single_page_pdf, "test.pdf")
    assert manifest.extract_status == "success"
    assert manifest.page_count == 1
    assert manifest.text_page_count == 1
    assert manifest.empty_page_count == 0
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "Hello" in pages[0].text
    assert pages[0].pdf_id.startswith("pdf_")
    assert len(pages[0].pdf_id) == 16


def test_multi_page_pdf_extraction(multi_page_pdf):
    manifest, pages = extract_pdf_file(multi_page_pdf, "multi.pdf")
    assert manifest.extract_status == "success"
    assert manifest.page_count == 3
    assert len(pages) == 3
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert pages[2].page_number == 3
    assert "Page 1" in pages[0].text


def test_empty_page_pdf(empty_page_pdf):
    manifest, pages = extract_pdf_file(empty_page_pdf, "empty.pdf")
    assert manifest.page_count == 1
    assert manifest.text_page_count == 0
    assert manifest.empty_page_count == 1
    assert manifest.needs_ocr is True
    assert len(pages) == 1
    assert pages[0].text == ""
    assert pages[0].char_count == 0


def test_pdf_id_stable(single_page_pdf):
    manifest1, _ = extract_pdf_file(single_page_pdf, "test.pdf")
    manifest2, _ = extract_pdf_file(single_page_pdf, "test.pdf")
    assert manifest1.pdf_id == manifest2.pdf_id
    assert manifest1.sha256 == manifest2.sha256


def test_page_number_starts_at_1(single_page_pdf):
    _, pages = extract_pdf_file(single_page_pdf, "test.pdf")
    assert pages[0].page_number == 1


def test_empty_directory(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    manifests, pages = extract_pdf_directory(d)
    assert manifests == []
    assert pages == []


def test_non_pdf_files_ignored(tmp_path, single_page_pdf):
    d = tmp_path / "pdfs"
    d.mkdir()
    (d / "readme.txt").write_text("not pdf", encoding="utf-8")
    import shutil
    shutil.copy(single_page_pdf, d / "report.pdf")
    manifests, pages = extract_pdf_directory(d)
    assert len(manifests) == 1
    assert manifests[0].source_pdf == "report.pdf"


def test_corrupt_pdf(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a valid pdf")

    manifest, pages = extract_pdf_file(bad, "bad.pdf")
    assert manifest.extract_status == "failed"
    assert manifest.error_message
    assert pages == []


def test_corrupt_pdf_does_not_crash_directory(tmp_path, multi_page_pdf):
    d = tmp_path / "pdfs"
    d.mkdir()
    (d / "bad.pdf").write_bytes(b"not valid pdf")
    import shutil
    shutil.copy(multi_page_pdf, d / "good.pdf")
    manifests, pages = extract_pdf_directory(d)
    assert len(manifests) == 2
    bad = [m for m in manifests if m.source_pdf == "bad.pdf"][0]
    assert bad.extract_status == "failed"
    good = [m for m in manifests if m.source_pdf == "good.pdf"][0]
    assert good.extract_status == "success"
    assert len(pages) == 3


def test_normalize_page_text():
    result = normalize_page_text("  hello   \r\nworld\t  ")
    assert "\r" not in result
    assert result == "hello\nworld"


def test_compute_sha256_stable(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"test content")
    h1 = compute_sha256(str(f))
    h2 = compute_sha256(str(f))
    assert h1 == h2


def test_generate_pdf_id_format():
    pid = generate_pdf_id("a" * 64)
    assert pid.startswith("pdf_")
    assert len(pid) == 16
