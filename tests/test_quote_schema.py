from ds_finance_concept.concept_builder.quote_schema import (
    QuoteCard,
    generate_quote_id,
    normalize_text,
)


def test_normalize_text_compresses_whitespace():
    assert normalize_text("  hello   world  ") == "hello world"


def test_normalize_text_handles_newlines_and_tabs():
    assert normalize_text("hello\nworld\tfoo") == "hello world foo"


def test_normalize_text_empty_string():
    assert normalize_text("") == ""


def test_normalize_text_only_whitespace():
    assert normalize_text("   \n\t  ") == ""


def test_generate_quote_id_is_stable():
    id1 = generate_quote_id("001.md", 0, "hello world")
    id2 = generate_quote_id("001.md", 0, "hello world")
    assert id1 == id2


def test_generate_quote_id_differs_for_different_file():
    id1 = generate_quote_id("001.md", 0, "hello")
    id2 = generate_quote_id("002.md", 0, "hello")
    assert id1 != id2


def test_generate_quote_id_differs_for_different_block_index():
    id1 = generate_quote_id("001.md", 0, "hello")
    id2 = generate_quote_id("001.md", 1, "hello")
    assert id1 != id2


def test_generate_quote_id_differs_for_different_text():
    id1 = generate_quote_id("001.md", 0, "hello")
    id2 = generate_quote_id("001.md", 0, "world")
    assert id1 != id2


def test_generate_quote_id_has_correct_format():
    qid = generate_quote_id("001.md", 0, "hello")
    assert qid.startswith("quote_")
    assert len(qid) == 18


def test_quote_card_char_count_matches():
    card = QuoteCard(
        quote_id="q",
        source_file="001.md",
        heading_path=["A"],
        block_type="heading",
        raw_text="hello world",
        normalized_text="hello world",
        char_count=11,
        line_start=1,
        line_end=1,
    )
    assert card.char_count == len(card.normalized_text)


def test_quote_card_is_frozen():
    card = QuoteCard(
        quote_id="q",
        source_file="f",
        heading_path=[],
        block_type="p",
        raw_text="r",
        normalized_text="n",
        char_count=1,
        line_start=1,
        line_end=1,
    )
    try:
        card.quote_id = "x"
        assert False, "QuoteCard should be frozen"
    except Exception:
        pass
