import os
from pathlib import Path

from .errors import PdfOpenError
from .manifest import (
    PdfManifest,
    PdfPage,
    compute_sha256,
    generate_pdf_id,
    normalize_page_text,
)

try:
    import fitz
except ImportError:
    fitz = None


def extract_pdf_file(pdf_path: Path, relative_path: str) -> tuple[PdfManifest, list[PdfPage]]:
    manifest = PdfManifest(
        source_pdf=pdf_path.name,
        relative_path=relative_path,
    )

    try:
        manifest.file_size_bytes = pdf_path.stat().st_size
    except OSError as e:
        manifest.extract_status = "failed"
        manifest.error_message = f"Cannot stat file: {e}"
        return manifest, []

    try:
        manifest.sha256 = compute_sha256(str(pdf_path))
    except OSError as e:
        manifest.extract_status = "failed"
        manifest.error_message = f"Cannot compute sha256: {e}"
        return manifest, []

    manifest.pdf_id = generate_pdf_id(manifest.sha256)

    if fitz is None:
        manifest.extract_status = "failed"
        manifest.error_message = "PyMuPDF (fitz) is not installed"
        return manifest, []

    doc = None
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        manifest.extract_status = "failed"
        manifest.error_message = f"Cannot open PDF: {e}"
        return manifest, []

    pages: list[PdfPage] = []
    try:
        manifest.page_count = doc.page_count
        for i in range(doc.page_count):
            page_number = i + 1
            try:
                page = doc[i]
                raw_text = page.get_text()
                text = normalize_page_text(raw_text)
            except Exception as e:
                text = ""
                if not manifest.error_message:
                    manifest.error_message = f"Page {page_number} extraction error: {e}"

            char_count = len(text)
            manifest.total_char_count += char_count

            if char_count > 0:
                manifest.text_page_count += 1
            else:
                manifest.empty_page_count += 1

            pages.append(PdfPage(
                pdf_id=manifest.pdf_id,
                source_pdf=manifest.source_pdf,
                relative_path=manifest.relative_path,
                page_number=page_number,
                text=text,
                char_count=char_count,
                extraction_method="pymupdf_text",
            ))
    finally:
        try:
            doc.close()
        except Exception:
            pass

    if manifest.empty_page_count > 0 and manifest.text_page_count == 0:
        manifest.needs_ocr = True
    elif manifest.empty_page_count > manifest.text_page_count:
        manifest.needs_ocr = True

    if manifest.text_page_count == 0 and manifest.page_count > 0:
        manifest.extract_status = "partial"
    elif manifest.error_message or manifest.empty_page_count > 0:
        manifest.extract_status = "partial"
    else:
        manifest.extract_status = "success"

    return manifest, pages


def extract_pdf_directory(pdf_dir: Path) -> tuple[list[PdfManifest], list[PdfPage]]:
    manifests: list[PdfManifest] = []
    all_pages: list[PdfPage] = []

    pdf_files = sorted(
        p for p in pdf_dir.rglob("*")
        if p.is_file() and p.suffix.lower() == ".pdf"
    )

    for pdf_path in pdf_files:
        rel_path = str(pdf_path.relative_to(pdf_dir))
        manifest, pages = extract_pdf_file(pdf_path, rel_path)
        manifests.append(manifest)
        all_pages.extend(pages)

    return manifests, all_pages
