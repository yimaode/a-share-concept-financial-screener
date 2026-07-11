import pytest
from pathlib import Path

from ds_finance_concept.concept_builder.errors import InputPathError
from ds_finance_concept.concept_builder.markdown_parser import (
    parse_markdown_dir,
    parse_markdown_file,
)


def test_heading_path_resolution(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("# H1\n## H2\n### H3\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    headings = [c for c in cards if c.block_type == "heading"]
    assert len(headings) == 3
    assert headings[0].heading_path == ["H1"]
    assert headings[1].heading_path == ["H1", "H2"]
    assert headings[2].heading_path == ["H1", "H2", "H3"]


def test_heading_reset_on_higher_level(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("## H2\n# H1\n## Another H2\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    headings = [c for c in cards if c.block_type == "heading"]
    assert headings[0].heading_path == ["H2"]
    assert headings[1].heading_path == ["H1"]
    assert headings[2].heading_path == ["H1", "Another H2"]


def test_paragraph_parsing(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("This is a paragraph.\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    paragraphs = [c for c in cards if c.block_type == "paragraph"]
    assert len(paragraphs) == 1
    assert paragraphs[0].normalized_text == "This is a paragraph."
    assert paragraphs[0].line_start == 1
    assert paragraphs[0].line_end == 1


def test_multi_line_paragraph(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("Line one\nLine two\nLine three\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    paragraphs = [c for c in cards if c.block_type == "paragraph"]
    assert len(paragraphs) == 1
    assert paragraphs[0].normalized_text == "Line one Line two Line three"
    assert paragraphs[0].line_start == 1
    assert paragraphs[0].line_end == 3


def test_paragraph_under_heading(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("# Title\n\nSome content here.\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    paras = [c for c in cards if c.block_type == "paragraph"]
    assert len(paras) == 1
    assert paras[0].heading_path == ["Title"]
    assert paras[0].normalized_text == "Some content here."


def test_blockquote_parsing(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("> This is a quote\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    quotes = [c for c in cards if c.block_type == "blockquote"]
    assert len(quotes) == 1
    assert "This is a quote" in quotes[0].normalized_text


def test_multi_line_blockquote(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("> Line one\n> Line two\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    quotes = [c for c in cards if c.block_type == "blockquote"]
    assert len(quotes) == 1
    assert "Line one" in quotes[0].normalized_text
    assert "Line two" in quotes[0].normalized_text
    assert quotes[0].line_start == 1
    assert quotes[0].line_end == 2


def test_list_item_parsing(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("- Item 1\n- Item 2\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    items = [c for c in cards if c.block_type == "list_item"]
    assert len(items) == 2
    assert items[0].normalized_text == "Item 1"
    assert items[1].normalized_text == "Item 2"
    assert items[0].line_start == 1
    assert items[1].line_start == 2


def test_ordered_list_item_parsing(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("1. First\n2. Second\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    items = [c for c in cards if c.block_type == "list_item"]
    assert len(items) == 2
    assert items[0].normalized_text == "First"
    assert items[1].normalized_text == "Second"


def test_code_block_skipped(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("Before\n```\ncode line 1\ncode line 2\n```\nAfter\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    texts = [c.normalized_text for c in cards]
    assert "code line 1" not in texts
    assert "code line 2" not in texts
    assert "Before" in texts
    assert "After" in texts


def test_empty_markdown_file(tmp_path):
    md = tmp_path / "empty.md"
    md.write_text("", encoding="utf-8")
    cards = parse_markdown_file(md)
    assert cards == []


def test_whitespace_only_markdown_file(tmp_path):
    md = tmp_path / "ws.md"
    md.write_text("   \n\n  \n", encoding="utf-8")
    cards = parse_markdown_file(md)
    assert cards == []


def test_empty_directory(tmp_path):
    d = tmp_path / "empty_dir"
    d.mkdir()
    cards = parse_markdown_dir(d)
    assert cards == []


def test_directory_with_md_files(tmp_path):
    d = tmp_path / "notes"
    d.mkdir()
    (d / "001.md").write_text("# H1\n\nText\n", encoding="utf-8")
    (d / "002.md").write_text("> Quote\n", encoding="utf-8")
    cards = parse_markdown_dir(d)
    assert len(cards) == 3


def test_input_dir_not_exists(tmp_path):
    with pytest.raises(InputPathError):
        parse_markdown_dir(tmp_path / "nonexistent")


def test_input_path_not_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello", encoding="utf-8")
    with pytest.raises(InputPathError):
        parse_markdown_dir(f)


def test_quote_id_consistency(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("Hello world\n", encoding="utf-8")
    cards1 = parse_markdown_file(md)
    cards2 = parse_markdown_file(md)
    assert cards1[0].quote_id == cards2[0].quote_id


def test_multiple_paragraphs_separated_by_empty_lines(tmp_path):
    md = tmp_path / "test.md"
    md.write_text("Para one.\n\nPara two.\n", encoding="utf-8")
    cards = parse_markdown_file(md)
    paras = [c for c in cards if c.block_type == "paragraph"]
    assert len(paras) == 2
    assert paras[0].normalized_text == "Para one."
    assert paras[1].normalized_text == "Para two."
