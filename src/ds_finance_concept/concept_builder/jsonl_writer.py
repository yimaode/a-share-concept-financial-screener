import json
from dataclasses import asdict
from pathlib import Path

from .errors import JsonlWriteError
from .quote_schema import QuoteCard


def write_quote_cards_jsonl(cards: list[QuoteCard], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_file.open("w", encoding="utf-8") as f:
            for card in cards:
                json.dump(asdict(card), f, ensure_ascii=False)
                f.write("\n")
    except Exception as e:
        raise JsonlWriteError(f"Failed to write JSONL to {output_file}: {e}") from e
