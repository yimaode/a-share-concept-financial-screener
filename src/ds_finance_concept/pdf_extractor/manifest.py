import hashlib
from dataclasses import dataclass, field


@dataclass
class PdfManifest:
    pdf_id: str = ""
    source_pdf: str = ""
    relative_path: str = ""
    sha256: str = ""
    file_size_bytes: int = 0
    page_count: int = 0
    extract_status: str = "failed"
    text_page_count: int = 0
    empty_page_count: int = 0
    total_char_count: int = 0
    needs_ocr: bool = False
    error_message: str = ""


@dataclass
class PdfPage:
    pdf_id: str = ""
    source_pdf: str = ""
    relative_path: str = ""
    page_number: int = 0
    text: str = ""
    char_count: int = 0
    extraction_method: str = "pymupdf_text"


def compute_sha256(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_pdf_id(sha256_hash: str) -> str:
    return f"pdf_{sha256_hash[:12]}"


def normalize_page_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()
