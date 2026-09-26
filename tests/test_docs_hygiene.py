"""Committed Markdown docs (e.g. AGENT_LOG.md) must not contain user-specific absolute paths."""

import re

import pytest

from adgen import config

# A drive or home prefix followed by an actual user name, e.g. C:\Users\alice or /home/alice.
USER_PATH = re.compile(r"[A-Za-z]:(\\\\|\\|/)+Users(\\\\|\\|/)+\w|/Users/\w|/home/\w", re.IGNORECASE)
DOCS = sorted(config.PROJECT_ROOT.glob("*.md"))


GOOGLE_API_KEY = re.compile(r"AIza[0-9A-Za-z_\-]{35}")


@pytest.mark.parametrize("path", DOCS, ids=[p.name for p in DOCS])
def test_doc_contains_no_user_paths(path):
    hits = [m.group(0) for m in USER_PATH.finditer(path.read_text(encoding="utf-8"))]
    assert not hits, f"user-specific path(s) in {path.name}: {hits}"


@pytest.mark.parametrize("path", DOCS, ids=[p.name for p in DOCS])
def test_doc_contains_no_api_keys(path):
    assert not GOOGLE_API_KEY.search(path.read_text(encoding="utf-8")), f"API-key-like string in {path.name}"


def test_ai_declaration_is_present_and_complete():
    text = (config.PROJECT_ROOT / "AI_DECLARATION_SUMMARY.md").read_text(encoding="utf-8")
    for required in ("Claude Code", "ChatGPT", "gemini-3.1-flash-image", "gemini-3.1-flash-lite",
                     "MCP", "none used", "human"):
        assert required.lower() in text.lower(), required
