"""LaTeX document class selection helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class LatexDocumentClass(str, Enum):
    """Supported LaTeX document classes for generated outputs."""

    article = "article"
    book = "book"
    beamer = "beamer"
    ctexart = "ctexart"
    ctexbook = "ctexbook"
    ctexbeamer = "ctexbeamer"

    @property
    def is_ctex(self) -> bool:
        return self.value.startswith("ctex")

    @property
    def family(self) -> str:
        if self in {LatexDocumentClass.book, LatexDocumentClass.ctexbook}:
            return "book"
        if self in {LatexDocumentClass.beamer, LatexDocumentClass.ctexbeamer}:
            return "beamer"
        return "article"

    @property
    def is_book(self) -> bool:
        return self.family == "book"

    @property
    def is_beamer(self) -> bool:
        return self.family == "beamer"

    def documentclass_line(self) -> str:
        if self.is_ctex:
            return rf"\documentclass[UTF8]{{{self.value}}}"
        return rf"\documentclass{{{self.value}}}"

    @classmethod
    def from_value(cls, value: str) -> "LatexDocumentClass":
        normalized = value.strip().lower()
        try:
            return cls(normalized)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(f"unsupported document class: {value}. Allowed: {allowed}.") from exc


class DocumentClassMode(str, Enum):
    """Document class selection strategy."""

    auto = "auto"
    article = LatexDocumentClass.article.value
    book = LatexDocumentClass.book.value
    beamer = LatexDocumentClass.beamer.value
    ctexart = LatexDocumentClass.ctexart.value
    ctexbook = LatexDocumentClass.ctexbook.value
    ctexbeamer = LatexDocumentClass.ctexbeamer.value

    @property
    def is_auto(self) -> bool:
        return self == DocumentClassMode.auto

    def resolved_class(self) -> LatexDocumentClass | None:
        if self.is_auto:
            return None
        return LatexDocumentClass.from_value(self.value)

    @classmethod
    def from_value(cls, value: str) -> "DocumentClassMode":
        normalized = value.strip().lower()
        try:
            return cls(normalized)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(f"--document-class must be one of: {allowed}.") from exc


@dataclass(frozen=True)
class DocumentClassResult:
    """Result of document class selection."""

    document_class: LatexDocumentClass
    confidence: float = 1.0
    reason: str = ""
    notes: list[str] = field(default_factory=list)
    source: str = "manual"

    def to_metadata(self) -> dict[str, object]:
        return {
            "document_class": self.document_class.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "notes": list(self.notes),
            "source": self.source,
        }


def normalize_document_class_result(
    *,
    document_class: str,
    confidence: object = 0.0,
    reason: str = "",
    notes: Iterable[object] = (),
    source: str = "llm",
) -> DocumentClassResult:
    """Normalize parsed model output into a supported document class result."""
    resolved_class = LatexDocumentClass.from_value(document_class)
    try:
        resolved_confidence = float(confidence)
    except (TypeError, ValueError):
        resolved_confidence = 0.0
    return DocumentClassResult(
        document_class=resolved_class,
        confidence=min(1.0, max(0.0, resolved_confidence)),
        reason=reason.strip(),
        notes=[str(note).strip() for note in notes if str(note).strip()],
        source=source,
    )


def manual_document_class_result(document_class: LatexDocumentClass) -> DocumentClassResult:
    """Build a deterministic document class result for manual selection."""
    return DocumentClassResult(
        document_class=document_class,
        confidence=1.0,
        reason="用户通过 --document-class 手动指定。",
        source="manual",
    )
