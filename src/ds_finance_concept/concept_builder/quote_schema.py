import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteCard:
    quote_id: str
    source_file: str
    heading_path: list[str]
    block_type: str
    raw_text: str
    normalized_text: str
    char_count: int
    line_start: int
    line_end: int


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def generate_quote_id(source_file: str, block_index: int, normalized_text: str) -> str:
    key = f"{source_file}:{block_index}:{normalized_text}"
    sha1_hash = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"quote_{sha1_hash}"
