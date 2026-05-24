"""Complex content candidates for PDF-to-LaTeX conversion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


BBox = tuple[float, float, float, float]


class ComplexContentKind(str, Enum):
    """Supported complex content categories."""

    table = "table"
    figure = "figure"
    layout_note = "layout_note"


class ComplexContentStrategy(str, Enum):
    """How one complex content candidate is represented in generated LaTeX."""

    latex = "latex"
    todo = "todo"
    pending_asset = "pending_asset"


class ComplexContentSource(str, Enum):
    """Where one complex content candidate was detected."""

    llm_latex = "llm_latex"
    llm_note = "llm_note"
    local_rule = "local_rule"


@dataclass(frozen=True)
class ComplexContentCandidate:
    """A JSON-safe description of one table, figure, or layout issue."""

    kind: ComplexContentKind
    strategy: ComplexContentStrategy
    page_number: int | None = None
    bbox: BBox | None = None
    source: ComplexContentSource = ComplexContentSource.llm_latex
    confidence: float = 0.0
    note: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            object.__setattr__(self, "kind", ComplexContentKind(self.kind))
        if isinstance(self.strategy, str):
            object.__setattr__(self, "strategy", ComplexContentStrategy(self.strategy))
        if isinstance(self.source, str):
            object.__setattr__(self, "source", ComplexContentSource(self.source))
        if self.page_number is not None and self.page_number <= 0:
            raise ValueError("complex content page_number must be positive.")
        if self.bbox is not None and len(self.bbox) != 4:
            raise ValueError("complex content bbox must contain four numbers.")
        object.__setattr__(self, "confidence", _clamp_confidence(self.confidence))
        object.__setattr__(self, "note", _normalize_note(self.note))

    def to_metadata(self) -> dict[str, object]:
        """Return a JSON-safe representation for project metadata."""
        data: dict[str, object] = {
            "kind": self.kind.value,
            "strategy": self.strategy.value,
            "source": self.source.value,
            "confidence": self.confidence,
        }
        if self.page_number is not None:
            data["page_number"] = self.page_number
        if self.bbox is not None:
            data["bbox"] = [float(value) for value in self.bbox]
        if self.note:
            data["note"] = self.note
        return data

    @classmethod
    def from_metadata(
        cls,
        data: Mapping[str, object],
    ) -> "ComplexContentCandidate":
        """Rebuild a candidate from metadata."""
        bbox = _coerce_bbox(data.get("bbox"))
        page_number = _coerce_int(data.get("page_number"))
        confidence = _coerce_float(data.get("confidence")) or 0.0
        return cls(
            kind=ComplexContentKind(str(data.get("kind", ""))),
            strategy=ComplexContentStrategy(str(data.get("strategy", ""))),
            page_number=page_number if page_number and page_number > 0 else None,
            bbox=bbox,
            source=ComplexContentSource(str(data.get("source", "llm_latex"))),
            confidence=confidence,
            note=str(data.get("note", "")),
        )


def complex_content_metadata(
    candidates: Sequence[ComplexContentCandidate],
) -> dict[str, object]:
    """Return project metadata for complex content candidates."""
    normalized = _dedupe_candidates(candidates)
    if not normalized:
        return {}
    return {
        "complex_content": {
            "schema_version": 1,
            "candidates": [candidate.to_metadata() for candidate in normalized],
        }
    }


def collect_complex_content_candidates(
    *,
    fragments: Sequence[str],
    notes: Sequence[str] = (),
) -> list[ComplexContentCandidate]:
    """Collect lightweight candidates from LLM LaTeX fragments and notes."""
    candidates: list[ComplexContentCandidate] = []
    for fragment in fragments:
        candidates.extend(_candidates_from_latex(fragment))
    for note in notes:
        candidates.extend(_candidates_from_note(note))
    return _dedupe_candidates(candidates)


def replace_unsupported_graphics_references(fragment: str) -> str:
    """Replace unsupported graphics includes with compile-safe TODO comments."""
    return _INCLUDEGRAPHICS_RE.sub(_graphics_todo_replacement, fragment)


def _candidates_from_latex(fragment: str) -> list[ComplexContentCandidate]:
    candidates: list[ComplexContentCandidate] = []
    if _TABLE_ENV_RE.search(fragment):
        candidates.append(
            ComplexContentCandidate(
                kind=ComplexContentKind.table,
                strategy=ComplexContentStrategy.latex,
                confidence=0.75,
                note="LLM 已将表格转换为 LaTeX 表格环境。",
            )
        )
    for match in _TODO_COMMENT_RE.finditer(fragment):
        text = match.group(1).strip()
        kind = _kind_from_text(text)
        if kind is None:
            continue
        candidates.append(
            ComplexContentCandidate(
                kind=kind,
                strategy=_strategy_from_todo_text(kind, text),
                page_number=_page_from_text(text),
                source=ComplexContentSource.llm_latex,
                confidence=0.5,
                note=text,
            )
        )
    for match in _INCLUDEGRAPHICS_RE.finditer(fragment):
        candidates.append(
            ComplexContentCandidate(
                kind=ComplexContentKind.figure,
                strategy=ComplexContentStrategy.pending_asset,
                source=ComplexContentSource.llm_latex,
                confidence=0.4,
                note=f"LLM 输出了当前未支持的图片引用：{match.group(0)}",
            )
        )
    return candidates


def _candidates_from_note(note: str) -> list[ComplexContentCandidate]:
    text = note.strip()
    kind = _kind_from_text(text)
    if kind is None:
        return []
    return [
        ComplexContentCandidate(
            kind=kind,
            strategy=_strategy_from_todo_text(kind, text),
            page_number=_page_from_text(text),
            source=ComplexContentSource.llm_note,
            confidence=0.45,
            note=text,
        )
    ]


def _graphics_todo_replacement(match: re.Match[str]) -> str:
    resource_match = re.search(r"\{([^{}\n]+)\}", match.group(0))
    resource = resource_match.group(1) if resource_match else "unknown"
    return (
        "% TODO: figure pending_asset - 当前阶段未生成图片裁切资源，"
        f"原图片资源：{resource}"
    )


def _kind_from_text(text: str) -> ComplexContentKind | None:
    lowered = text.lower()
    if any(token in lowered for token in ("table", "tabular", "表格")):
        return ComplexContentKind.table
    if any(token in lowered for token in ("figure", "image", "graphics", "图", "图片", "图表")):
        return ComplexContentKind.figure
    if any(token in lowered for token in ("sidebar", "margin", "column", "layout", "边栏", "旁注", "多栏", "版面")):
        return ComplexContentKind.layout_note
    return None


def _strategy_from_todo_text(
    kind: ComplexContentKind,
    text: str,
) -> ComplexContentStrategy:
    lowered = text.lower()
    if kind == ComplexContentKind.figure or any(
        token in lowered for token in ("pending_asset", "裁切", "includegraphics")
    ):
        return ComplexContentStrategy.pending_asset
    if "tabular" in lowered or "array" in lowered:
        return ComplexContentStrategy.latex
    return ComplexContentStrategy.todo


def _page_from_text(text: str) -> int | None:
    patterns = [
        r"(?:page|PAGE)\s*(\d+)",
        r"第\s*(\d+)\s*页",
        r"页码\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _dedupe_candidates(
    candidates: Sequence[ComplexContentCandidate],
) -> list[ComplexContentCandidate]:
    seen: set[tuple[object, ...]] = set()
    deduped: list[ComplexContentCandidate] = []
    for candidate in candidates:
        key = (
            candidate.kind.value,
            candidate.strategy.value,
            candidate.page_number,
            candidate.bbox,
            candidate.source.value,
            candidate.note,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _normalize_note(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clamp_confidence(value: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, confidence))


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _coerce_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _coerce_bbox(value: object) -> BBox | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) != 4:
        return None
    try:
        return tuple(float(item) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


_TABLE_ENV_RE = re.compile(
    r"\\begin\{(?:tabular|tabularx|array|longtable)\b",
    re.IGNORECASE,
)
_TODO_COMMENT_RE = re.compile(r"(?m)^\s*%\s*TODO:\s*(.+)$")
_INCLUDEGRAPHICS_RE = re.compile(
    r"\\includegraphics(?:\[[^\]]*\])?\{[^{}\n]+\}",
    re.IGNORECASE,
)
