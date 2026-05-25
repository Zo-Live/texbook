"""Utilities for normalizing trusted LaTeX text fragments."""

from __future__ import annotations

import re


_LITERAL_NEWLINE_ESCAPE_RE = re.compile(r"\\r\\n|\\[nr](?=\s|\\|%|$)")


def normalize_latex_fragment_newlines(text: str) -> str:
    """Restore escaped line separators without splitting normal LaTeX commands."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _LITERAL_NEWLINE_ESCAPE_RE.sub("\n", normalized)
    return normalized.strip()
