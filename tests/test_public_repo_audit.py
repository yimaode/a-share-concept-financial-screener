from pathlib import Path

from scripts.check_public_repo import audit


def test_public_repo_audit_detects_private_directory_and_secret(tmp_path):
    private = tmp_path / "data" / "guru_notes"
    private.mkdir(parents=True)
    (private / "notes.md").write_text("private", encoding="utf-8")
    (tmp_path / "leak.txt").write_text("sk-" + "x" * 24, encoding="utf-8")
    issues = audit(tmp_path)
    assert any("private/generated directory" in issue for issue in issues)
    assert any("OpenAI-style token" in issue for issue in issues)


def test_public_repo_audit_accepts_clean_tree(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "concepts.json").write_text(
        '{"concepts":[{"concept_id":"demo","source_quote_ids":[]}]}',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("public", encoding="utf-8")
    assert audit(tmp_path) == []
