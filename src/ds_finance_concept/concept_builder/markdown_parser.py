import re
from pathlib import Path

from .errors import InputPathError, MarkdownParseError
from .quote_schema import QuoteCard, generate_quote_id, normalize_text


def _extract_heading(line: str) -> tuple[int | None, str | None]:
    m = re.match(r"^(#{1,6})\s+(.+)$", line)
    if m:
        return len(m.group(1)), m.group(2).strip()
    return None, None


def _is_code_fence(line: str) -> bool:
    return line.strip().startswith("```")


def _extract_blockquote(line: str) -> str | None:
    m = re.match(r"^>\s?(.*)$", line)
    if m:
        return m.group(1)
    return None


def _extract_list_item(line: str) -> str | None:
    m = re.match(r"^(\s{0,3})([-*]|\d+\.)\s+(.+)$", line)
    if m:
        return m.group(3).strip()
    return None


def parse_markdown_file(path: Path) -> list[QuoteCard]:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        raise MarkdownParseError(f"Failed to read file {path}: {e}") from e

    source_file = path.name
    lines = content.split("\n")
    cards: list[QuoteCard] = []
    heading_path: list[str] = []
    block_index = 0
    in_code_block = False

    block_type: str | None = None
    block_lines: list[str] = []
    block_line_start = 0

    def flush_block() -> None:
        nonlocal block_index, block_type, block_lines
        if block_type is None or not block_lines:
            block_type = None
            block_lines = []
            return

        raw_text = "\n".join(block_lines)
        normalized = normalize_text(raw_text)

        if normalized:
            quote_id = generate_quote_id(source_file, block_index, normalized)
            cards.append(
                QuoteCard(
                    quote_id=quote_id,
                    source_file=source_file,
                    heading_path=list(heading_path),
                    block_type=block_type,
                    raw_text=raw_text,
                    normalized_text=normalized,
                    char_count=len(normalized),
                    line_start=block_line_start,
                    line_end=block_line_start + len(block_lines) - 1,
                )
            )
            block_index += 1

        block_type = None
        block_lines = []

    for i, line in enumerate(lines):
        lineno = i + 1

        if in_code_block:
            if _is_code_fence(line):
                in_code_block = False
            continue

        if _is_code_fence(line):
            in_code_block = True
            flush_block()
            continue

        level, heading_text = _extract_heading(line)
        if level is not None:
            flush_block()
            heading_path = heading_path[: level - 1]
            heading_path.append(heading_text)
            raw_text = line.strip()
            normalized = normalize_text(raw_text)
            if normalized:
                quote_id = generate_quote_id(source_file, block_index, normalized)
                cards.append(
                    QuoteCard(
                        quote_id=quote_id,
                        source_file=source_file,
                        heading_path=list(heading_path),
                        block_type="heading",
                        raw_text=raw_text,
                        normalized_text=normalized,
                        char_count=len(normalized),
                        line_start=lineno,
                        line_end=lineno,
                    )
                )
                block_index += 1
            continue

        blockquote_text = _extract_blockquote(line)
        if blockquote_text is not None:
            if block_type == "blockquote":
                block_lines.append(blockquote_text)
            else:
                flush_block()
                block_type = "blockquote"
                block_lines = [blockquote_text]
                block_line_start = lineno
            continue

        list_text = _extract_list_item(line)
        if list_text is not None:
            flush_block()
            block_type = "list_item"
            block_lines = [list_text]
            block_line_start = lineno
            continue

        if not line.strip():
            flush_block()
            continue

        if block_type == "paragraph":
            block_lines.append(line.strip())
        elif block_type == "list_item":
            block_lines.append(line.strip())
        else:
            flush_block()
            block_type = "paragraph"
            block_lines = [line.strip()]
            block_line_start = lineno

    flush_block()
    return cards


def parse_markdown_dir(input_dir: Path) -> list[QuoteCard]:
    if not input_dir.exists():
        raise InputPathError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise InputPathError(f"Input path is not a directory: {input_dir}")

    md_files = sorted(input_dir.rglob("*.md"))
    all_cards: list[QuoteCard] = []
    for md_file in md_files:
        cards = parse_markdown_file(md_file)
        all_cards.extend(cards)
    return all_cards
