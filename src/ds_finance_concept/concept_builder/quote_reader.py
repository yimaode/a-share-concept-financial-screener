import json
from pathlib import Path

from .errors import QuoteReaderError


def read_quote_cards_jsonl(input_file: Path) -> list[dict]:
    if not input_file.exists():
        raise QuoteReaderError(f"Quote file not found: {input_file}")
    if not input_file.is_file():
        raise QuoteReaderError(f"Quote path is not a file: {input_file}")

    quotes: list[dict] = []
    try:
        with input_file.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    quotes.append(json.loads(stripped))
                except json.JSONDecodeError as e:
                    raise QuoteReaderError(
                        f"Invalid JSON at line {line_num} in {input_file}: {e}"
                    ) from e
    except QuoteReaderError:
        raise
    except Exception as e:
        raise QuoteReaderError(f"Failed to read {input_file}: {e}") from e

    return quotes
