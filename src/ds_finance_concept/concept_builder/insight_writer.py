import json
from pathlib import Path

from .errors import JsonlWriteError
from .insight_schema import InsightCard, insight_card_to_dict, validate_insight_card


def write_insight_cards_jsonl(cards: list[InsightCard], output_file: Path) -> None:
    for card in cards:
        validate_insight_card(card)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_file.open("w", encoding="utf-8") as f:
            if not cards:
                return
            for card in cards:
                json.dump(insight_card_to_dict(card), f, ensure_ascii=False)
                f.write("\n")
    except Exception as e:
        raise JsonlWriteError(f"Failed to write JSONL to {output_file}: {e}") from e
