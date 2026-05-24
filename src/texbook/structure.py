"""Document structure planning for directory-style LaTeX projects."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from .extract.base import PdfPageContext


class StructureMode(str, Enum):
    """Available project structure planning modes."""

    auto = "auto"
    off = "off"
    local = "local"
    llm = "llm"


class StructureItemKind(str, Enum):
    """Supported top-level structure item kinds."""

    frontmatter = "frontmatter"
    chapter = "chapter"
    appendix = "appendix"


class StructurePlanSource(str, Enum):
    """Where a structure plan came from."""

    bookmark = "bookmark"
    llm_toc = "llm-toc"
    llm_headings = "llm-headings"
    local_headings = "local-headings"
    chunk_fallback = "chunk-fallback"


@dataclass(frozen=True)
class StructurePlannerOptions:
    """Runtime options for project structure planning."""

    mode: StructureMode = StructureMode.auto
    chunk_pages: int = 8
    max_pages: int = 32

    def __post_init__(self) -> None:
        if self.chunk_pages <= 0:
            raise ValueError("structure chunk_pages must be positive.")
        if self.max_pages <= 0:
            raise ValueError("structure max_pages must be positive.")
        if isinstance(self.mode, str):
            object.__setattr__(self, "mode", StructureMode(self.mode))


@dataclass(frozen=True)
class StructurePlanItem:
    """One top-level item in a planned document structure."""

    kind: StructureItemKind
    title: str
    start_page: int
    end_page: int
    confidence: float = 0.0
    source: StructurePlanSource = StructurePlanSource.local_headings

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            object.__setattr__(self, "kind", StructureItemKind(self.kind))
        if isinstance(self.source, str):
            object.__setattr__(self, "source", StructurePlanSource(self.source))
        title = _normalize_title(self.title)
        if not title:
            raise ValueError("structure item title must not be empty.")
        if self.start_page <= 0 or self.end_page <= 0:
            raise ValueError("structure item pages must be positive.")
        if self.end_page < self.start_page:
            raise ValueError("structure item end_page must be >= start_page.")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "confidence", _clamp_confidence(self.confidence))


@dataclass(frozen=True)
class StructurePlan:
    """A validated top-level structure plan for a PDF selection."""

    items: list[StructurePlanItem]
    source: StructurePlanSource
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)
    inspected_pages: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.source, str):
            object.__setattr__(self, "source", StructurePlanSource(self.source))
        if not self.items:
            raise ValueError("structure plan must contain at least one item.")

        previous_end = 0
        normalized_items: list[StructurePlanItem] = []
        for item in self.items:
            if not isinstance(item, StructurePlanItem):
                raise TypeError("structure plan items must be StructurePlanItem.")
            if item.start_page <= previous_end:
                raise ValueError("structure plan items must be ordered and non-overlapping.")
            previous_end = item.end_page
            normalized_items.append(item)

        object.__setattr__(self, "items", normalized_items)
        object.__setattr__(self, "confidence", _clamp_confidence(self.confidence))
        object.__setattr__(
            self,
            "inspected_pages",
            sorted({int(page) for page in self.inspected_pages if int(page) > 0}),
        )

    @property
    def page_numbers(self) -> list[int]:
        """Return all physical PDF pages covered by the plan."""
        pages: list[int] = []
        for item in self.items:
            pages.extend(range(item.start_page, item.end_page + 1))
        return pages

    def to_metadata(self) -> dict[str, object]:
        """Return a JSON-safe metadata representation."""
        return {
            "source": self.source.value,
            "confidence": self.confidence,
            "inspected_pages": self.inspected_pages,
            "items": [
                {
                    "kind": item.kind.value,
                    "title": item.title,
                    "start_page": item.start_page,
                    "end_page": item.end_page,
                    "confidence": item.confidence,
                    "source": item.source.value,
                }
                for item in self.items
            ],
        }

    @classmethod
    def from_metadata(cls, data: Mapping[str, object]) -> "StructurePlan":
        """Rebuild a structure plan from a cached metadata representation."""
        source = StructurePlanSource(str(data.get("source", "")))
        items_value = data.get("items")
        if not isinstance(items_value, list):
            raise ValueError("cached structure plan items must be a list.")

        items: list[StructurePlanItem] = []
        for item_value in items_value:
            if not isinstance(item_value, Mapping):
                continue
            kind = StructureItemKind(str(item_value.get("kind", "")))
            item_source = StructurePlanSource(str(item_value.get("source", source.value)))
            start_page = _coerce_int(item_value.get("start_page"))
            end_page = _coerce_int(item_value.get("end_page"))
            if start_page is None or end_page is None:
                continue
            items.append(
                StructurePlanItem(
                    kind=kind,
                    title=str(item_value.get("title", "")),
                    start_page=start_page,
                    end_page=end_page,
                    confidence=_coerce_float(item_value.get("confidence")) or 0.0,
                    source=item_source,
                )
            )

        confidence = _coerce_float(data.get("confidence")) or 0.0
        inspected_pages = _coerce_positive_int_list(data.get("inspected_pages"))
        notes_value = data.get("notes", [])
        notes = (
            [str(note) for note in notes_value if str(note).strip()]
            if isinstance(notes_value, list)
            else []
        )
        return cls(
            items=items,
            source=source,
            confidence=confidence,
            notes=notes,
            inspected_pages=inspected_pages,
        )


@dataclass(frozen=True)
class BookmarkEntry:
    """A normalized PDF bookmark/table-of-contents entry."""

    level: int
    title: str
    page_number: int


@dataclass(frozen=True)
class PageHeadingCandidate:
    """A compact title-like page text clue."""

    page_number: int
    text: str
    font_size: float
    block_type: str = "text"


@dataclass(frozen=True)
class StructureEvidence:
    """Local evidence available to the structure planner."""

    source_title: str
    total_pages: int
    selected_pages: list[int]
    bookmarks: list[BookmarkEntry] = field(default_factory=list)
    heading_candidates: list[PageHeadingCandidate] = field(default_factory=list)
    page_starts: dict[int, str] = field(default_factory=dict)

    @property
    def effective_pages(self) -> list[int]:
        """Return selected pages, or all physical pages if no explicit selection exists."""
        if self.selected_pages:
            return self.selected_pages
        return list(range(1, self.total_pages + 1))

    def selected_page_set(self) -> set[int]:
        """Return the pages allowed by the current conversion selection."""
        return set(self.effective_pages)

    def format_for_llm(self, *, max_chars: int = 18000) -> str:
        """Build compact text evidence for the LLM structure planner."""
        lines = [
            f"PDF 标题：{self.source_title}",
            f"PDF 总页数：{self.total_pages}",
            "当前转换页码："
            + _format_page_ranges(self.effective_pages),
        ]

        if self.bookmarks:
            lines.extend(["", "PDF 书签线索（level | page | title）："])
            for entry in self.bookmarks[:120]:
                lines.append(f"{entry.level} | {entry.page_number} | {entry.title}")

        if self.heading_candidates:
            lines.extend(["", "标题候选（page | font_size | type | text）："])
            for candidate in self.heading_candidates[:240]:
                lines.append(
                    f"{candidate.page_number} | {candidate.font_size:.1f} | "
                    f"{candidate.block_type} | {candidate.text}"
                )

        if self.page_starts:
            lines.extend(["", "页面开头文本："])
            for page_number in sorted(self.page_starts)[:120]:
                text = self.page_starts[page_number]
                lines.append(f"第 {page_number} 页：{text}")

        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "\n[结构线索已截断]"

    def to_metadata(self) -> dict[str, object]:
        """Return a JSON-safe metadata representation."""
        return {
            "source_title": self.source_title,
            "total_pages": self.total_pages,
            "selected_pages": [int(page) for page in self.selected_pages],
            "effective_pages": self.effective_pages,
            "bookmarks": [
                {
                    "level": entry.level,
                    "title": entry.title,
                    "page_number": entry.page_number,
                }
                for entry in self.bookmarks
            ],
            "heading_candidates": [
                {
                    "page_number": candidate.page_number,
                    "text": candidate.text,
                    "font_size": candidate.font_size,
                    "block_type": candidate.block_type,
                }
                for candidate in self.heading_candidates
            ],
            "page_starts": {
                str(page_number): self.page_starts[page_number]
                for page_number in sorted(self.page_starts)
            },
        }

    @classmethod
    def from_metadata(cls, data: Mapping[str, object]) -> "StructureEvidence":
        """Rebuild structure evidence from cached metadata."""
        bookmarks_value = data.get("bookmarks", [])
        bookmarks: list[BookmarkEntry] = []
        if isinstance(bookmarks_value, list):
            for item in bookmarks_value:
                if not isinstance(item, Mapping):
                    continue
                page_number = _coerce_int(item.get("page_number"))
                level = _coerce_int(item.get("level"))
                if page_number is None or level is None:
                    continue
                bookmarks.append(
                    BookmarkEntry(
                        level=level,
                        title=str(item.get("title", "")),
                        page_number=page_number,
                    )
                )

        headings_value = data.get("heading_candidates", [])
        heading_candidates: list[PageHeadingCandidate] = []
        if isinstance(headings_value, list):
            for item in headings_value:
                if not isinstance(item, Mapping):
                    continue
                page_number = _coerce_int(item.get("page_number"))
                font_size = _coerce_float(item.get("font_size"))
                if page_number is None or font_size is None:
                    continue
                heading_candidates.append(
                    PageHeadingCandidate(
                        page_number=page_number,
                        text=str(item.get("text", "")),
                        font_size=font_size,
                        block_type=str(item.get("block_type", "text")),
                    )
                )

        page_starts: dict[int, str] = {}
        starts_value = data.get("page_starts", {})
        if isinstance(starts_value, Mapping):
            for key, value in starts_value.items():
                page_number = _coerce_int(key)
                if page_number is None:
                    continue
                page_starts[page_number] = str(value)

        total_pages = _coerce_int(data.get("total_pages"))
        if total_pages is None:
            raise ValueError("cached structure evidence total_pages is invalid.")
        return cls(
            source_title=str(data.get("source_title", "")),
            total_pages=total_pages,
            selected_pages=_coerce_positive_int_list(data.get("selected_pages")),
            bookmarks=bookmarks,
            heading_candidates=heading_candidates,
            page_starts=page_starts,
        )


def build_plan_from_bookmarks(
    evidence: StructureEvidence,
    *,
    min_items: int = 2,
) -> StructurePlan | None:
    """Build a structure plan from PDF bookmarks when they are trustworthy enough."""
    selected_pages = evidence.effective_pages
    if not selected_pages:
        return None
    selected_set = set(selected_pages)
    min_selected_page = min(selected_pages)
    max_selected_page = max(selected_pages)

    candidates: list[BookmarkEntry] = []
    for entry in evidence.bookmarks:
        if entry.page_number not in selected_set:
            continue
        title = _normalize_title(entry.title)
        if not title or _is_page_number_title(title):
            continue
        candidates.append(
            BookmarkEntry(
                level=max(1, int(entry.level)),
                title=title,
                page_number=entry.page_number,
            )
        )

    if len(candidates) < min_items:
        return None

    min_level = min(entry.level for entry in candidates)
    top_entries = [
        entry
        for entry in candidates
        if entry.level == min_level and _looks_like_top_level_title(entry.title)
    ]
    if len(top_entries) < min_items:
        top_entries = [entry for entry in candidates if entry.level == min_level]
    if len(top_entries) < min_items:
        return None

    deduped: list[BookmarkEntry] = []
    seen_pages: set[int] = set()
    for entry in top_entries:
        if entry.page_number in seen_pages:
            continue
        seen_pages.add(entry.page_number)
        deduped.append(entry)

    if len(deduped) < min_items:
        return None
    if any(later.page_number <= earlier.page_number for earlier, later in zip(deduped, deduped[1:])):
        return None

    items: list[StructurePlanItem] = []
    if deduped[0].page_number > min_selected_page:
        items.append(
            StructurePlanItem(
                kind=StructureItemKind.frontmatter,
                title="前置内容",
                start_page=min_selected_page,
                end_page=deduped[0].page_number - 1,
                confidence=0.75,
                source=StructurePlanSource.bookmark,
            )
        )

    for index, entry in enumerate(deduped):
        next_start = deduped[index + 1].page_number if index + 1 < len(deduped) else max_selected_page + 1
        end_page = min(next_start - 1, max_selected_page)
        if end_page < entry.page_number:
            continue
        kind = (
            StructureItemKind.appendix
            if _looks_like_appendix_title(entry.title)
            else StructureItemKind.chapter
        )
        items.append(
            StructurePlanItem(
                kind=kind,
                title=entry.title,
                start_page=entry.page_number,
                end_page=end_page,
                confidence=0.9,
                source=StructurePlanSource.bookmark,
            )
        )

    chapter_count = sum(item.kind == StructureItemKind.chapter for item in items)
    if chapter_count < min_items:
        return None

    return StructurePlan(
        items=items,
        source=StructurePlanSource.bookmark,
        confidence=0.9,
        inspected_pages=[entry.page_number for entry in deduped],
    )


def build_local_heading_plan(evidence: StructureEvidence) -> StructurePlan | None:
    """Build a low-confidence plan from local heading candidates only."""
    selected_pages = evidence.effective_pages
    if not selected_pages:
        return None
    selected_set = set(selected_pages)
    max_selected_page = max(selected_pages)

    candidates: list[PageHeadingCandidate] = []
    seen_pages: set[int] = set()
    for candidate in evidence.heading_candidates:
        if candidate.page_number not in selected_set or candidate.page_number in seen_pages:
            continue
        title = _normalize_title(candidate.text)
        if not title or _is_page_number_title(title):
            continue
        if not _looks_like_top_level_title(title):
            continue
        candidates.append(
            PageHeadingCandidate(
                page_number=candidate.page_number,
                text=title,
                font_size=candidate.font_size,
                block_type=candidate.block_type,
            )
        )
        seen_pages.add(candidate.page_number)

    if len(candidates) < 2:
        return None
    if any(later.page_number <= earlier.page_number for earlier, later in zip(candidates, candidates[1:])):
        return None

    items: list[StructurePlanItem] = []
    for index, candidate in enumerate(candidates):
        next_start = candidates[index + 1].page_number if index + 1 < len(candidates) else max_selected_page + 1
        end_page = min(next_start - 1, max_selected_page)
        if end_page < candidate.page_number:
            continue
        kind = (
            StructureItemKind.appendix
            if _looks_like_appendix_title(candidate.text)
            else StructureItemKind.chapter
        )
        items.append(
            StructurePlanItem(
                kind=kind,
                title=candidate.text,
                start_page=candidate.page_number,
                end_page=end_page,
                confidence=0.45,
                source=StructurePlanSource.local_headings,
            )
        )

    if sum(item.kind == StructureItemKind.chapter for item in items) < 2:
        return None

    return StructurePlan(
        items=items,
        source=StructurePlanSource.local_headings,
        confidence=0.45,
        inspected_pages=[candidate.page_number for candidate in candidates],
        notes=["本地标题线索置信度较低，建议人工复核章节边界。"],
    )


def build_chunk_fallback_plan(
    page_groups: Sequence[Sequence[int]],
    *,
    title_prefix: str = "分块",
    note: str = "结构规划失败，已回退到按 LLM chunk 划分章节文件。",
) -> StructurePlan:
    """Build a synthetic chunk-based fallback structure plan."""
    items = [
        StructurePlanItem(
            kind=StructureItemKind.chapter,
            title=f"{title_prefix} {index}",
            start_page=min(group),
            end_page=max(group),
            confidence=0.0,
            source=StructurePlanSource.chunk_fallback,
        )
        for index, group in enumerate(page_groups, start=1)
        if group
    ]
    if not items:
        raise ValueError("fallback plan requires at least one page group.")
    return StructurePlan(
        items=items,
        source=StructurePlanSource.chunk_fallback,
        confidence=0.0,
        notes=[note],
        inspected_pages=[],
    )


def normalize_llm_structure_plan(
    *,
    items: Sequence[dict[str, object]],
    source: StructurePlanSource,
    confidence: float,
    selected_pages: Sequence[int],
    inspected_pages: Sequence[int] | None = None,
    notes: Sequence[str] | None = None,
) -> StructurePlan:
    """Validate and normalize a raw LLM structure plan."""
    if not selected_pages:
        raise ValueError("structure plan needs selected pages.")
    selected_set = set(int(page) for page in selected_pages)
    min_selected_page = min(selected_set)
    max_selected_page = max(selected_set)

    normalized_items: list[StructurePlanItem] = []
    for raw_item in items:
        title = _normalize_title(str(raw_item.get("title", "")))
        if not title or _is_page_number_title(title):
            continue
        start_page = _coerce_int(raw_item.get("start_page"))
        end_page = _coerce_int(raw_item.get("end_page"))
        if start_page is None or end_page is None:
            continue
        start_page = max(start_page, min_selected_page)
        end_page = min(end_page, max_selected_page)
        if end_page < start_page:
            continue
        if not any(page in selected_set for page in range(start_page, end_page + 1)):
            continue

        raw_kind = str(raw_item.get("kind", "chapter")).strip().lower()
        if raw_kind in {"frontmatter", "preface", "toc", "contents", "前置内容", "目录"}:
            kind = StructureItemKind.frontmatter
        elif raw_kind in {"appendix", "appendices", "附录"} or _looks_like_appendix_title(title):
            kind = StructureItemKind.appendix
        else:
            kind = StructureItemKind.chapter

        item_confidence = _coerce_float(raw_item.get("confidence"))
        normalized_items.append(
            StructurePlanItem(
                kind=kind,
                title=title,
                start_page=start_page,
                end_page=end_page,
                confidence=confidence if item_confidence is None else item_confidence,
                source=source,
            )
        )

    normalized_items.sort(key=lambda item: (item.start_page, item.end_page))
    non_overlapping: list[StructurePlanItem] = []
    previous_end = 0
    for item in normalized_items:
        if item.start_page <= previous_end:
            if item.end_page <= previous_end:
                continue
            item = StructurePlanItem(
                kind=item.kind,
                title=item.title,
                start_page=previous_end + 1,
                end_page=item.end_page,
                confidence=item.confidence,
                source=item.source,
            )
        non_overlapping.append(item)
        previous_end = item.end_page

    if not non_overlapping:
        raise ValueError("LLM structure plan did not contain usable items.")
    if not any(item.kind == StructureItemKind.chapter for item in non_overlapping):
        raise ValueError("LLM structure plan did not contain any chapters.")

    return StructurePlan(
        items=non_overlapping,
        source=source,
        confidence=confidence,
        notes=[str(note) for note in notes or [] if str(note).strip()],
        inspected_pages=list(inspected_pages or []),
    )


def plan_hash_payload(plan: StructurePlan | None) -> dict[str, object] | None:
    """Return a compact stable payload suitable for cache keys."""
    if plan is None:
        return None
    return {
        "source": plan.source.value,
        "confidence": plan.confidence,
        "items": [
            {
                "kind": item.kind.value,
                "title": item.title,
                "start_page": item.start_page,
                "end_page": item.end_page,
            }
            for item in plan.items
        ],
    }


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clamp_confidence(value: float) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, confidence))


def _is_page_number_title(title: str) -> bool:
    normalized = title.strip()
    return bool(
        re.fullmatch(
            r"(?:第?\s*)?(?:[ivxlcdmIVXLCDM]+|\d+|[一二三四五六七八九十百零〇]+)\s*(?:页|p\.?)?",
            normalized,
        )
    )


def _looks_like_top_level_title(title: str) -> bool:
    normalized = title.strip()
    if _is_page_number_title(normalized):
        return False
    patterns = [
        r"^第\s*[一二三四五六七八九十百零〇\d]+\s*[章节篇部卷]",
        r"^[一二三四五六七八九十百零〇\d]+\s*[\.、]\s*\S+",
        r"^Chapter\s+\d+",
        r"^CHAPTER\s+\d+",
        r"^Appendix\b",
        r"^附录",
        r"^目录$",
        r"^绪论$",
        r"^前言$",
    ]
    if any(re.search(pattern, normalized) for pattern in patterns):
        return True
    return len(normalized) >= 2 and not normalized.isdigit()


def _looks_like_appendix_title(title: str) -> bool:
    return bool(re.search(r"^(附录|Appendix\b|APPENDIX\b)", title.strip()))


def _format_page_ranges(pages: Sequence[int]) -> str:
    if not pages:
        return "[无]"
    sorted_pages = sorted({int(page) for page in pages})
    ranges: list[str] = []
    start = previous = sorted_pages[0]
    for page in sorted_pages[1:]:
        if page == previous + 1:
            previous = page
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = page
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


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


def _coerce_positive_int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    pages: list[int] = []
    for item in value:
        page = _coerce_int(item)
        if page is not None and page > 0:
            pages.append(page)
    return pages


def summarize_pages_for_structure(pages: Sequence[PdfPageContext]) -> list[int]:
    """Return page numbers represented by a structure-planning page batch."""
    return [page.page_number for page in pages]
