import json
import pytest

from ds_finance_concept.concept_builder.errors import QuoteReaderError
from ds_finance_concept.concept_builder.quote_reader import read_quote_cards_jsonl


def test_read_two_lines(tmp_path):
    f = tmp_path / "quotes.jsonl"
    f.write_text(
        json.dumps({"quote_id": "q1", "text": "a"}, ensure_ascii=False) + "\n" +
        json.dumps({"quote_id": "q2", "text": "b"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    quotes = read_quote_cards_jsonl(f)
    assert len(quotes) == 2
    assert quotes[0]["quote_id"] == "q1"
    assert quotes[1]["quote_id"] == "q2"


def test_empty_file_returns_empty_list(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text("", encoding="utf-8")
    quotes = read_quote_cards_jsonl(f)
    assert quotes == []


def test_file_not_exists_raises(tmp_path):
    f = tmp_path / "nonexistent.jsonl"
    with pytest.raises(QuoteReaderError, match="not found"):
        read_quote_cards_jsonl(f)


def test_invalid_json_line_raises_with_line_number(tmp_path):
    f = tmp_path / "bad.jsonl"
    f.write_text(
        json.dumps({"quote_id": "q1"}, ensure_ascii=False) + "\n" +
        "not valid json\n" +
        json.dumps({"quote_id": "q3"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(QuoteReaderError, match="line 2"):
        read_quote_cards_jsonl(f)


def test_blank_lines_skipped(tmp_path):
    f = tmp_path / "with_blanks.jsonl"
    f.write_text(
        "\n" +
        json.dumps({"quote_id": "q1"}, ensure_ascii=False) + "\n" +
        "\n" +
        json.dumps({"quote_id": "q2"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    quotes = read_quote_cards_jsonl(f)
    assert len(quotes) == 2
