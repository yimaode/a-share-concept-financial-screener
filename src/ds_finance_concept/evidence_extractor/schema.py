import hashlib
from dataclasses import dataclass, field


@dataclass
class EvidenceHit:
    evidence_id: str = ""
    concept_id: str = ""
    concept_name: str = ""
    polarity: str = ""
    keyword_group: str = ""
    keyword: str = ""
    sentence: str = ""
    context_before: str = ""
    context_after: str = ""
    negation_detected: bool = False
    truncated: bool = False
    pdf_id: str = ""
    source_pdf: str = ""
    relative_path: str = ""
    page_number: int = 0
    char_count: int = 0


def generate_evidence_id(
    concept_id: str,
    polarity: str,
    keyword: str,
    pdf_id: str,
    page_number: int,
    sentence: str,
) -> str:
    key = f"{concept_id}|{polarity}|{keyword}|{pdf_id}|{page_number}|{sentence}"
    sha = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"ev_{sha}"


EVIDENCE_CSV_FIELDS = [
    "evidence_id",
    "concept_id",
    "concept_name",
    "polarity",
    "keyword_group",
    "keyword",
    "sentence",
    "negation_detected",
    "truncated",
    "source_pdf",
    "relative_path",
    "page_number",
]
