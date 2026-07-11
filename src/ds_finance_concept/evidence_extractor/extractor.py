import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .errors import ConceptsNotFrozenError, EvidenceExtractorError, PageReadError
from .schema import EvidenceHit, generate_evidence_id

SENTENCE_DELIMITERS = re.compile(r"[。！？；.!?;]")
MAX_SENTENCE_LENGTH = 500

# 年报封面、合规勾选项和前瞻性声明中的“风险”不是公司经营反证，不能进入概念打分。
# 这些句子仍可在原始 PDF 中查到，但不应被当作关键经营证据。
NON_SUBSTANTIVE_PATTERNS = [
    "前瞻性陈述的风险声明", "是否存在被控股股东", "是否存在违反规定决策程序",
    "半数以上董事无法保证", "董事会决议通过的本报告期利润分配预案",
    "敬请关注",
]

NEGATION_WORDS = [
    "不", "未", "没有", "无", "下降", "减少", "下滑",
    "疲软", "不足", "承压", "不及预期",
]


def _split_sentences(text: str) -> list[str]:
    result: list[str] = []
    start = 0
    for match in SENTENCE_DELIMITERS.finditer(text):
        end = match.end()
        sentence = text[start:end].strip()
        if sentence:
            result.append(sentence)
        start = end
    remaining = text[start:].strip()
    if remaining:
        result.append(remaining)
    return result


def _has_negation(sentence: str) -> bool:
    return any(nw in sentence for nw in NEGATION_WORDS)


def _normalize_sentence(sentence: str) -> str:
    return re.sub(r"\s+", " ", sentence).strip()


def _is_non_substantive_sentence(sentence: str) -> bool:
    return any(pattern in sentence for pattern in NON_SUBSTANTIVE_PATTERNS)


def _expand_keywords(keywords_data: Any) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if isinstance(keywords_data, dict):
        for group, words in keywords_data.items():
            if isinstance(words, list):
                for word in words:
                    if isinstance(word, str) and word.strip():
                        pairs.append((group, word.strip()))
    elif isinstance(keywords_data, list):
        for item in keywords_data:
            if isinstance(item, str) and item.strip():
                pairs.append(("", item.strip()))
    return pairs


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    if not path.exists():
        raise PageReadError(f"Pages file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                raise PageReadError(
                    f"Invalid JSON at line {line_num} in {path}: {e}"
                ) from e
    return records


def _read_concepts(path: Path) -> dict:
    if not path.exists():
        raise EvidenceExtractorError(f"Concepts file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "frozen":
        raise ConceptsNotFrozenError(
            f"Concepts file status is {data.get('status', 'unknown')!r}, must be 'frozen'"
        )
    return data


def _build_keyword_index(concepts: list[dict]) -> list[dict]:
    index: list[dict] = []
    for c in concepts:
        cid = c.get("concept_id", "")
        cname = c.get("name", "")

        for polarity, key in [("positive", "positive_keywords"), ("negative", "negative_keywords")]:
            kw_data = c.get(key, {})
            pairs = _expand_keywords(kw_data)
            for group, word in pairs:
                index.append({
                    "concept_id": cid,
                    "concept_name": cname,
                    "polarity": polarity,
                    "keyword_group": group,
                    "keyword": word,
                })
    return index


def _extract_context(sentences: list[str], idx: int) -> tuple[str, str]:
    before = sentences[idx - 1] if idx > 0 else ""
    after = sentences[idx + 1] if idx < len(sentences) - 1 else ""
    return before, after


def _normalize_hit_key(hit: EvidenceHit) -> tuple:
    return (
        hit.concept_id, hit.polarity, hit.keyword,
        hit.pdf_id, hit.page_number, hit.sentence,
    )


def extract_evidence(
    concepts_file: Path,
    pages_file: Path,
    manifest_file: Path,
) -> tuple[list[EvidenceHit], list[str], list[dict], dict]:
    concepts_data = _read_concepts(concepts_file)
    concepts = concepts_data.get("concepts", [])

    keyword_index = _build_keyword_index(concepts)
    if not keyword_index:
        return [], [], [], {"total_hits": 0}

    pages = _read_jsonl(pages_file)

    manifest_ids: set[str] = set()
    manifest_pdfs: list[dict] = []
    if manifest_file.exists():
        manifest_records = _read_jsonl(manifest_file)
        for m in manifest_records:
            mid = m.get("pdf_id", "")
            if mid:
                manifest_ids.add(mid)
            manifest_pdfs.append(m)

    hits: list[EvidenceHit] = []
    seen: set[tuple] = set()
    warnings: list[str] = []

    for page in pages:
        pdf_id = page.get("pdf_id", "")
        source_pdf = page.get("source_pdf", "")
        relative_path = page.get("relative_path", "")
        page_number = page.get("page_number", 0)
        text = page.get("text", "")

        if manifest_ids and pdf_id and pdf_id not in manifest_ids:
            warnings.append(f"pdf_id {pdf_id} not found in manifest")

        if not text:
            continue

        sentences = _split_sentences(text)

        for ki in keyword_index:
            kw = ki["keyword"]
            for s_idx, sentence in enumerate(sentences):
                if kw not in sentence:
                    continue

                sentence = _normalize_sentence(sentence)
                if _is_non_substantive_sentence(sentence):
                    continue

                truncated = False
                if len(sentence) > MAX_SENTENCE_LENGTH:
                    sentence = sentence[:MAX_SENTENCE_LENGTH]
                    truncated = True

                negation = _has_negation(sentence)

                context_before, context_after = _extract_context(sentences, s_idx)

                hit = EvidenceHit(
                    evidence_id="",
                    concept_id=ki["concept_id"],
                    concept_name=ki["concept_name"],
                    polarity=ki["polarity"],
                    keyword_group=ki["keyword_group"],
                    keyword=kw,
                    sentence=sentence,
                    context_before=context_before,
                    context_after=context_after,
                    negation_detected=negation,
                    truncated=truncated,
                    pdf_id=pdf_id,
                    source_pdf=source_pdf,
                    relative_path=relative_path,
                    page_number=page_number,
                    char_count=len(sentence),
                )

                hit.evidence_id = generate_evidence_id(
                    hit.concept_id, hit.polarity, hit.keyword,
                    hit.pdf_id, hit.page_number, hit.sentence,
                )

                key = _normalize_hit_key(hit)
                if key in seen:
                    continue
                seen.add(key)

                hits.append(hit)

    hits.sort(key=lambda h: (
        h.relative_path,
        h.page_number,
        h.concept_id,
        h.polarity,
        h.keyword,
    ))

    stats = _build_stats(hits, concepts)
    return hits, warnings, manifest_pdfs, stats


def _build_stats(hits: list[EvidenceHit], concepts: list[dict]) -> dict:
    stats: dict = {
        "total_hits": len(hits),
        "concepts": {},
    }

    concept_name_map = {c["concept_id"]: c.get("name", "") for c in concepts}

    for hit in hits:
        cid = hit.concept_id
        if cid not in stats["concepts"]:
            stats["concepts"][cid] = {
                "concept_name": concept_name_map.get(cid, cid),
                "positive_hits": 0,
                "negative_hits": 0,
                "keywords": defaultdict(int),
                "pdfs": defaultdict(int),
            }
        cs = stats["concepts"][cid]

        if hit.polarity == "positive":
            cs["positive_hits"] += 1
        else:
            cs["negative_hits"] += 1

        cs["keywords"][hit.keyword] += 1
        cs["pdfs"][hit.source_pdf] += 1

    for cid in stats["concepts"]:
        cs = stats["concepts"][cid]
        cs["keywords"] = dict(sorted(cs["keywords"].items(), key=lambda x: -x[1]))
        cs["pdfs"] = dict(sorted(cs["pdfs"].items(), key=lambda x: -x[1]))

    return stats
