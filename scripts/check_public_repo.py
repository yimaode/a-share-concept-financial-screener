"""Fail fast when common private artifacts or credentials enter the repository."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_DIRS = (
    "data/guru_notes", "data/raw_pdfs", "raw_pdfs", "outputs",
    "concept_workspace", "private_notes", "inputs", "credentials", "cookies",
)
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3"}
SECRET_PATTERNS = {
    "OpenAI-style token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{30,}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".json", ".yml", ".yaml", ".csv", ".txt"}


def audit(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    for relative in FORBIDDEN_DIRS:
        path = root / relative
        if path.exists() and any(path.rglob("*")):
            issues.append(f"private/generated directory present: {relative}")

    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(root)
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            issues.append(f"sensitive file type: {relative}")
        if path.stat().st_size > 5 * 1024 * 1024:
            issues.append(f"unexpected file larger than 5 MiB: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2 * 1024 * 1024:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                issues.append(f"possible {label}: {relative}")

    concepts_file = root / "config" / "concepts.json"
    if concepts_file.exists():
        data = json.loads(concepts_file.read_text(encoding="utf-8"))
        for concept in data.get("concepts", []):
            if concept.get("source_quote_ids"):
                issues.append(
                    f"private quote provenance remains in concept: {concept.get('concept_id', '?')}"
                )
    return sorted(set(issues))


def main() -> int:
    issues = audit()
    if issues:
        print("Public repository audit FAILED:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Public repository audit PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
