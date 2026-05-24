"""LLM-driven PDF to LaTeX conversion pipeline."""

import re
import sys
from collections import deque
from contextlib import contextmanager
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Thread
from typing import Iterable, Iterator, Protocol, Sequence, TextIO

from ..convert.latex_converter import LatexConverter
from ..convert.project import LatexProjectBuilder, LatexProjectResult, LatexProjectSection
from ..extract.base import ImageRenderOptions, PdfDocumentChunk, PdfPageContext
from ..extract.text_extractor import TextExtractor
from ..structure import (
    StructureEvidence,
    StructureMode,
    StructurePlan,
    StructurePlanItem,
    StructurePlanSource,
    StructurePlannerOptions,
    build_chunk_fallback_plan,
    build_local_heading_plan,
    build_plan_from_bookmarks,
    normalize_llm_structure_plan,
    summarize_pages_for_structure,
)
from .cache import ChunkCacheOptions, ChunkCacheRun, StructurePlanCacheRun
from .client import LLMChunkResult, LLMStructurePlanResult
from .presets import PromptPreset, default_prompt_preset


class LatexChunkClient(Protocol):
    """Client interface used by the conversion pipeline."""

    def generate_latex_chunk(
        self,
        *,
        document_title: str,
        pages: Sequence[PdfPageContext],
        chunk_index: int,
        total_chunks: int,
        previous_latex_tail: str = "",
        extra_prompt: str = "",
        prompt_preset: PromptPreset | None = None,
    ) -> LLMChunkResult:
        """Generate LaTeX for one page chunk."""

    def generate_document_title(
        self,
        *,
        fallback_title: str,
        title_evidence: str,
        extra_prompt: str = "",
        prompt_preset: PromptPreset | None = None,
    ) -> str:
        """Generate a document title from collected conversion evidence."""

    def generate_structure_plan(
        self,
        *,
        document_title: str,
        evidence: StructureEvidence,
        pages: Sequence[PdfPageContext] = (),
        inspected_pages: Sequence[int] = (),
        stage: str = "toc",
        extra_prompt: str = "",
    ) -> LLMStructurePlanResult:
        """Generate or assess a chapter-level structure plan."""


@dataclass
class LLMConversionResult:
    """Complete LLM conversion output."""

    latex: str
    notes: list[str] = field(default_factory=list)


@dataclass
class _CollectedConversion:
    """Shared output collected before final LaTeX assembly."""

    title: str
    fragments: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class _CollectedProjectConversion:
    """Project conversion output grouped by semantic sections."""

    title: str
    sections: list[LatexProjectSection] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    structure_plan: StructurePlan | None = None


class LLMPdfConverter:
    """Convert PDF lecture notes to LaTeX using page context and an LLM."""

    def __init__(
        self,
        client: LatexChunkClient,
        *,
        extractor: TextExtractor | None = None,
        chunk_pages: int = 4,
        image_dpi: int = 160,
        image_options: ImageRenderOptions | None = None,
        prefetch_chunks: int = 1,
        cache_options: ChunkCacheOptions | None = None,
        extra_prompt: str = "",
        prompt_preset: PromptPreset | None = None,
        title_source: str = "filename",
        manual_title: str | None = None,
        show_date: bool = False,
        structure_options: StructurePlannerOptions | None = None,
        progress_stream: TextIO | None = None,
        progress_interval: float = 0.1,
    ):
        if chunk_pages <= 0:
            raise ValueError("chunk_pages must be positive.")
        if image_dpi <= 0:
            raise ValueError("image_dpi must be positive.")
        if prefetch_chunks < 0:
            raise ValueError("prefetch_chunks must be non-negative.")
        if title_source not in {"filename", "llm"}:
            raise ValueError("title_source must be filename or llm.")

        resolved_manual_title = None
        if manual_title is not None:
            resolved_manual_title = _normalize_title_text(manual_title)
            if not resolved_manual_title:
                raise ValueError("manual_title must not be empty.")
        if resolved_manual_title is not None and title_source == "llm":
            raise ValueError("manual_title cannot be used with title_source=llm.")

        self.client = client
        self.extractor = extractor or TextExtractor()
        self.chunk_pages = chunk_pages
        self.image_dpi = image_dpi
        self.image_options = image_options or ImageRenderOptions(
            dpi=image_dpi,
            dpi_max=image_dpi,
        )
        self.prefetch_chunks = prefetch_chunks
        self.cache_options = (
            cache_options if cache_options is not None and cache_options.enabled else None
        )
        self.extra_prompt = extra_prompt
        self.prompt_preset = prompt_preset or default_prompt_preset()
        self.title_source = title_source
        self.manual_title = resolved_manual_title
        self.show_date = show_date
        self.structure_options = structure_options or StructurePlannerOptions(
            mode=StructureMode.auto
        )
        self.progress_spinner = _LlmWaitSpinner(progress_stream, progress_interval)
        self.document_builder = LatexConverter()
        self.project_builder = LatexProjectBuilder()

    def convert(
        self,
        pdf_path: Path,
        *,
        pages: Sequence[int] | None = None,
    ) -> LLMConversionResult:
        collected = self._collect_conversion(pdf_path, pages=pages)
        return LLMConversionResult(
            latex=self.document_builder.convert_fragments(
                title=collected.title,
                fragments=collected.fragments,
                notes=collected.notes,
                show_date=self.show_date,
            ),
            notes=collected.notes,
        )

    def convert_project(
        self,
        pdf_path: Path,
        *,
        pages: Sequence[int] | None = None,
    ) -> LatexProjectResult:
        """Convert a PDF into an in-memory directory-style LaTeX project."""
        if self.structure_options.mode == StructureMode.off:
            collected = self._collect_conversion(pdf_path, pages=pages)
            return self.project_builder.build(
                title=collected.title,
                fragments=collected.fragments,
                notes=collected.notes,
                show_date=self.show_date,
            )

        collected = self._collect_project_conversion(pdf_path, pages=pages)
        if collected.structure_plan is None:
            return self.project_builder.build(
                title=collected.title,
                fragments=[
                    fragment
                    for section in collected.sections
                    for fragment in section.fragments
                ],
                notes=collected.notes,
                show_date=self.show_date,
            )
        return self.project_builder.build_from_plan(
            title=collected.title,
            sections=collected.sections,
            structure_plan=collected.structure_plan,
            notes=collected.notes,
            show_date=self.show_date,
        )

    def _collect_conversion(
        self,
        pdf_path: Path,
        *,
        pages: Sequence[int] | None = None,
    ) -> _CollectedConversion:
        fragments: list[str] = []
        notes: list[str] = []
        previous_latex_tail = ""
        fallback_title = pdf_path.stem
        working_title = self.manual_title or fallback_title
        title_evidence = _TitleEvidenceCollector(filename_title=fallback_title)
        saw_chunk = False
        cache_run: ChunkCacheRun | None = None

        chunks = self.extractor.iter_context_chunks(
            pdf_path,
            pages=pages,
            image_dpi=self.image_dpi,
            include_images=True,
            image_options=self.image_options,
            chunk_size=self.chunk_pages,
        )

        chunk_iterator = _iter_prefetched_chunks(chunks, self.prefetch_chunks)
        try:
            for chunk in chunk_iterator:
                if not saw_chunk:
                    fallback_title = chunk.title
                    working_title = self.manual_title or fallback_title
                    title_evidence = _TitleEvidenceCollector(
                        filename_title=fallback_title,
                    )
                    if self.cache_options is not None:
                        cache_run = ChunkCacheRun(
                            options=self.cache_options,
                            pdf_path=pdf_path,
                            pages=pages,
                            document_title=working_title,
                            chunk_pages=self.chunk_pages,
                            image_dpi=self.image_dpi,
                            image_options=self.image_options,
                            extra_prompt=self.extra_prompt,
                            prompt_preset=self.prompt_preset,
                            title_source=self.title_source,
                        )
                saw_chunk = True
                try:
                    result = (
                        cache_run.read(chunk, previous_latex_tail)
                        if cache_run is not None
                        else None
                    )
                    if result is None:
                        message = (
                            f"Waiting for LLM chunk "
                            f"{chunk.chunk_index}/{chunk.total_chunks}"
                        )
                        with self.progress_spinner.spin(message):
                            result = self.client.generate_latex_chunk(
                                document_title=working_title,
                                pages=chunk.pages,
                                chunk_index=chunk.chunk_index,
                                total_chunks=chunk.total_chunks,
                                previous_latex_tail=previous_latex_tail,
                                extra_prompt=self.extra_prompt,
                                prompt_preset=self.prompt_preset,
                            )
                        if cache_run is not None:
                            cache_run.write(chunk, previous_latex_tail, result)
                finally:
                    _release_page_images(chunk.pages)

                previous_latex_tail = _append_tail(
                    previous_latex_tail,
                    result.latex,
                    has_previous_fragment=bool(fragments),
                )
                title_evidence.add_chunk(chunk, result.latex)
                fragments.append(result.latex)
                notes.extend(result.notes)
        finally:
            close = getattr(chunk_iterator, "close", None)
            if close is not None:
                close()

        if not saw_chunk:
            raise ValueError("No pages were selected for conversion.")

        document_title = self._resolve_document_title(
            fallback_title=fallback_title,
            working_title=working_title,
            title_evidence=title_evidence.build(),
        )
        return _CollectedConversion(
            title=document_title,
            fragments=fragments,
            notes=notes,
        )

    def _collect_project_conversion(
        self,
        pdf_path: Path,
        *,
        pages: Sequence[int] | None = None,
    ) -> _CollectedProjectConversion:
        fallback_title = pdf_path.stem
        working_title = self.manual_title or fallback_title
        title_evidence = _TitleEvidenceCollector(filename_title=fallback_title)
        evidence = self.extractor.extract_structure_evidence(pdf_path, pages=pages)
        selected_pages = evidence.effective_pages
        if not selected_pages:
            raise ValueError("No pages were selected for conversion.")

        structure_cache_run: StructurePlanCacheRun | None = None
        if self.cache_options is not None:
            structure_cache_run = StructurePlanCacheRun(
                options=self.cache_options,
                pdf_path=pdf_path,
                pages=pages,
                document_title=working_title,
                image_dpi=self.image_dpi,
                image_options=self.image_options,
                extra_prompt=self.extra_prompt,
                structure_options=self.structure_options,
                evidence=evidence,
            )
            structure_cache_run.write_evidence()

        structure_plan = self._resolve_structure_plan(
            pdf_path=pdf_path,
            evidence=evidence,
            document_title=working_title,
            pages=pages,
            cache_run=structure_cache_run,
        )
        chunk_groups = _plan_chunk_groups(
            structure_plan,
            chunk_pages=self.chunk_pages,
            allowed_pages=selected_pages,
        )
        fallback_plan_used = structure_plan.source.value == "chunk-fallback"
        plan_notes = list(structure_plan.notes)

        sections: list[LatexProjectSection] = []
        notes: list[str] = []
        previous_latex_tail = ""
        cache_run: ChunkCacheRun | None = None
        if self.cache_options is not None:
            cache_run = ChunkCacheRun(
                options=self.cache_options,
                pdf_path=pdf_path,
                pages=pages,
                document_title=working_title,
                chunk_pages=self.chunk_pages,
                image_dpi=self.image_dpi,
                image_options=self.image_options,
                extra_prompt=self.extra_prompt,
                prompt_preset=self.prompt_preset,
                title_source=self.title_source,
                structure_plan=structure_plan,
            )

        total_chunks = sum(len(groups) for _, groups in chunk_groups)
        chunk_index = 0
        for item, groups in chunk_groups:
            section_fragments: list[str] = []
            for group in groups:
                chunk_index += 1
                chunk = self._load_context_chunk(
                    pdf_path,
                    page_numbers=group,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                )
                try:
                    result = (
                        cache_run.read(chunk, previous_latex_tail)
                        if cache_run is not None
                        else None
                    )
                    if result is None:
                        message = f"Waiting for LLM chunk {chunk_index}/{total_chunks}"
                        with self.progress_spinner.spin(message):
                            result = self.client.generate_latex_chunk(
                                document_title=working_title,
                                pages=chunk.pages,
                                chunk_index=chunk_index,
                                total_chunks=total_chunks,
                                previous_latex_tail=previous_latex_tail,
                                extra_prompt=self.extra_prompt,
                                prompt_preset=self.prompt_preset,
                            )
                        if cache_run is not None:
                            cache_run.write(chunk, previous_latex_tail, result)
                finally:
                    _release_page_images(chunk.pages)

                previous_latex_tail = _append_tail(
                    previous_latex_tail,
                    result.latex,
                    has_previous_fragment=bool(section_fragments or sections),
                )
                title_evidence.add_chunk(chunk, result.latex)
                section_fragments.append(result.latex)
                notes.extend(result.notes)
            sections.append(LatexProjectSection(item=item, fragments=section_fragments))

        document_title = self._resolve_document_title(
            fallback_title=fallback_title,
            working_title=working_title,
            title_evidence=title_evidence.build(),
        )
        return _CollectedProjectConversion(
            title=document_title,
            sections=sections,
            notes=[*plan_notes, *notes],
            structure_plan=None if fallback_plan_used else structure_plan,
        )

    def _resolve_structure_plan(
        self,
        *,
        pdf_path: Path,
        evidence: StructureEvidence,
        document_title: str,
        pages: Sequence[int] | None,
        cache_run: StructurePlanCacheRun | None = None,
    ) -> StructurePlan:
        options = self.structure_options
        selected_pages = evidence.effective_pages
        if options.mode in {StructureMode.auto, StructureMode.local}:
            bookmark_plan = build_plan_from_bookmarks(evidence)
            if bookmark_plan is not None:
                if cache_run is not None:
                    cache_run.write_local_plan(bookmark_plan)
                return bookmark_plan
            if options.mode == StructureMode.local:
                local_plan = build_local_heading_plan(evidence)
                if local_plan is not None:
                    if cache_run is not None:
                        cache_run.write_local_plan(local_plan)
                    return local_plan
                fallback_plan = build_chunk_fallback_plan(
                    _chunk_page_numbers(selected_pages, self.chunk_pages),
                    note="本地结构线索不足，已回退到按 LLM chunk 划分章节文件。",
                )
                if cache_run is not None:
                    cache_run.write_local_plan(
                        fallback_plan,
                        filename="structure-fallback.json",
                    )
                return fallback_plan

        if options.mode in {StructureMode.auto, StructureMode.llm}:
            try:
                llm_plan = self._generate_llm_structure_plan(
                    pdf_path=pdf_path,
                    evidence=evidence,
                    document_title=document_title,
                    pages=pages,
                    cache_run=cache_run,
                )
            except Exception:
                if options.mode == StructureMode.llm:
                    raise
                llm_plan = None
            if llm_plan is not None:
                return llm_plan
            if options.mode == StructureMode.llm:
                raise ValueError("LLM did not return a usable structure plan.")

        local_plan = build_local_heading_plan(evidence)
        if local_plan is not None and options.mode == StructureMode.local:
            if cache_run is not None:
                cache_run.write_local_plan(local_plan)
            return local_plan
        fallback_plan = build_chunk_fallback_plan(
            _chunk_page_numbers(selected_pages, self.chunk_pages),
        )
        if cache_run is not None:
            cache_run.write_local_plan(
                fallback_plan,
                filename="structure-fallback.json",
            )
        return fallback_plan

    def _generate_llm_structure_plan(
        self,
        *,
        pdf_path: Path,
        evidence: StructureEvidence,
        document_title: str,
        pages: Sequence[int] | None,
        cache_run: StructurePlanCacheRun | None = None,
    ) -> StructurePlan | None:
        selected_pages = evidence.effective_pages
        page_batches = _chunk_page_numbers(
            selected_pages[: self.structure_options.max_pages],
            self.structure_options.chunk_pages,
        )
        inspected_pages: list[int] = []
        last_result: LLMStructurePlanResult | None = None
        request_index = 0

        for batch in page_batches:
            request_index += 1
            chunk_pages = self._load_structure_pages(
                pdf_path,
                page_numbers=batch,
            )
            inspected_pages.extend(summarize_pages_for_structure(chunk_pages))
            try:
                result = (
                    cache_run.read(
                        stage="toc",
                        request_index=request_index,
                        pages=chunk_pages,
                        inspected_pages=inspected_pages,
                    )
                    if cache_run is not None
                    else None
                )
                if result is None:
                    with self.progress_spinner.spin("Waiting for LLM structure plan"):
                        result = self.client.generate_structure_plan(
                            document_title=document_title,
                            evidence=evidence,
                            pages=chunk_pages,
                            inspected_pages=inspected_pages,
                            stage="toc",
                            extra_prompt=self.extra_prompt,
                        )
            finally:
                _release_page_images(chunk_pages)

            last_result = result
            if result.status == "complete":
                plan = normalize_llm_structure_plan(
                    items=result.plan,
                    source=StructurePlanSource.llm_toc,
                    confidence=result.confidence,
                    selected_pages=selected_pages,
                    inspected_pages=inspected_pages,
                    notes=[*result.notes, result.reason],
                )
                if cache_run is not None:
                    cache_run.write(
                        stage="toc",
                        request_index=request_index,
                        pages=chunk_pages,
                        inspected_pages=inspected_pages,
                        result=result,
                        normalized_plan=plan,
                    )
                return plan
            if cache_run is not None:
                cache_run.write(
                    stage="toc",
                    request_index=request_index,
                    pages=chunk_pages,
                    inspected_pages=inspected_pages,
                    result=result,
                )
            if result.status == "insufficient":
                break

        heading_result = (
            cache_run.read(
                stage="headings",
                request_index=1,
                pages=[],
                inspected_pages=inspected_pages,
            )
            if cache_run is not None
            else None
        )
        if heading_result is None:
            with self.progress_spinner.spin("Waiting for LLM heading structure plan"):
                heading_result = self.client.generate_structure_plan(
                    document_title=document_title,
                    evidence=evidence,
                    pages=[],
                    inspected_pages=inspected_pages,
                    stage="headings",
                    extra_prompt=self.extra_prompt,
                )
        if heading_result.status != "complete":
            if cache_run is not None:
                cache_run.write(
                    stage="headings",
                    request_index=1,
                    pages=[],
                    inspected_pages=inspected_pages,
                    result=heading_result,
                )
            if last_result is not None and last_result.reason:
                return None
            return None

        plan = normalize_llm_structure_plan(
            items=heading_result.plan,
            source=StructurePlanSource.llm_headings,
            confidence=heading_result.confidence,
            selected_pages=selected_pages,
            inspected_pages=inspected_pages,
            notes=[*heading_result.notes, heading_result.reason],
        )
        if cache_run is not None:
            cache_run.write(
                stage="headings",
                request_index=1,
                pages=[],
                inspected_pages=inspected_pages,
                result=heading_result,
                normalized_plan=plan,
            )
        return plan

    def _load_context_chunk(
        self,
        pdf_path: Path,
        *,
        page_numbers: Sequence[int],
        chunk_index: int,
        total_chunks: int,
    ) -> PdfDocumentChunk:
        chunks = self.extractor.iter_context_chunks(
            pdf_path,
            pages=page_numbers,
            image_dpi=self.image_dpi,
            include_images=True,
            image_options=self.image_options,
            chunk_size=len(page_numbers),
        )
        iterator = iter(chunks)
        try:
            chunk = next(iterator)
        except StopIteration as exc:
            raise ValueError("No pages were selected for conversion.") from exc
        finally:
            close = getattr(iterator, "close", None)
            if close is not None:
                close()
        return PdfDocumentChunk(
            source_file=chunk.source_file,
            title=chunk.title,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            pages=chunk.pages,
        )

    def _load_structure_pages(
        self,
        pdf_path: Path,
        *,
        page_numbers: Sequence[int],
    ) -> list[PdfPageContext]:
        chunks = self.extractor.iter_context_chunks(
            pdf_path,
            pages=page_numbers,
            image_dpi=self.image_dpi,
            include_images=True,
            image_options=self.image_options,
            chunk_size=max(1, len(page_numbers)),
        )
        iterator = iter(chunks)
        try:
            chunk = next(iterator)
        except StopIteration:
            return []
        finally:
            close = getattr(iterator, "close", None)
            if close is not None:
                close()
        return chunk.pages

    def _resolve_document_title(
        self,
        *,
        fallback_title: str,
        working_title: str,
        title_evidence: str,
    ) -> str:
        if self.manual_title is not None:
            return self.manual_title
        if self.title_source != "llm":
            return working_title

        try:
            with self.progress_spinner.spin("Waiting for LLM title"):
                title = self.client.generate_document_title(
                    fallback_title=fallback_title,
                    title_evidence=title_evidence,
                    extra_prompt=self.extra_prompt,
                    prompt_preset=self.prompt_preset,
                )
        except Exception:
            return fallback_title

        return _normalize_title_text(title) or fallback_title


def _chunk_pages(
    pages: Sequence[PdfPageContext],
    chunk_size: int,
) -> list[list[PdfPageContext]]:
    return [list(pages[index : index + chunk_size]) for index in range(0, len(pages), chunk_size)]


def _chunk_page_numbers(
    pages: Sequence[int],
    chunk_size: int,
) -> list[list[int]]:
    return [
        list(pages[index : index + chunk_size])
        for index in range(0, len(pages), chunk_size)
    ]


def _plan_chunk_groups(
    plan: StructurePlan,
    *,
    chunk_pages: int,
    allowed_pages: Sequence[int] | None = None,
) -> list[tuple[StructurePlanItem, list[list[int]]]]:
    allowed = list(allowed_pages) if allowed_pages is not None else plan.page_numbers
    groups: list[tuple[StructurePlanItem, list[list[int]]]] = []
    for item in plan.items:
        item_pages = [
            page
            for page in allowed
            if item.start_page <= page <= item.end_page
        ]
        if not item_pages:
            continue
        groups.append((item, _chunk_page_numbers(item_pages, chunk_pages)))
    return groups


def _tail(text: str, max_chars: int = 2000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _append_tail(
    previous_tail: str,
    fragment: str,
    *,
    has_previous_fragment: bool,
    max_chars: int = 2000,
) -> str:
    if not has_previous_fragment:
        return _tail(fragment, max_chars)
    return _tail(previous_tail + "\n\n" + fragment, max_chars)


def _release_page_images(pages: Sequence[PdfPageContext]) -> None:
    for page in pages:
        page.image_base64 = None


_SECTION_TITLE_RE = re.compile(r"\\(?:sub)*section\*?\{([^{}\n]+)\}")


class _TitleEvidenceCollector:
    """Collect compact title clues without retaining page images."""

    def __init__(self, *, filename_title: str):
        self.filename_title = filename_title
        self._headings: list[str] = []
        self._page_starts: list[str] = []
        self._latex_sections: list[str] = []
        self._seen: set[str] = set()

    def add_chunk(self, chunk: PdfDocumentChunk, latex_fragment: str) -> None:
        for page in chunk.pages:
            for block in page.text_blocks:
                if block.block_type != "heading":
                    continue
                self._add_unique(
                    self._headings,
                    f"第 {page.page_number} 页 heading：{block.text}",
                    max_items=40,
                )

            plain_text = _normalize_title_text(page.plain_text)
            if plain_text:
                self._add_unique(
                    self._page_starts,
                    f"第 {page.page_number} 页开头：{plain_text[:300]}",
                    max_items=40,
                )

        for match in _SECTION_TITLE_RE.finditer(latex_fragment):
            self._add_unique(
                self._latex_sections,
                match.group(1),
                max_items=40,
            )

    def build(self, max_chars: int = 12000) -> str:
        lines = [f"PDF 文件名：{self.filename_title}"]
        if self._headings:
            lines.extend(["", "页面 heading 线索：", *self._headings])
        if self._latex_sections:
            lines.extend(["", "已生成 LaTeX 章节线索：", *self._latex_sections])
        if self._page_starts:
            lines.extend(["", "页面开头文本线索：", *self._page_starts])

        evidence = "\n".join(lines)
        if len(evidence) <= max_chars:
            return evidence
        return evidence[:max_chars].rstrip() + "\n[标题线索已截断]"

    def _add_unique(self, target: list[str], value: str, *, max_items: int) -> None:
        normalized = _normalize_title_text(value)
        if not normalized or normalized in self._seen or len(target) >= max_items:
            return
        self._seen.add(normalized)
        target.append(normalized)


def _normalize_title_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class _LlmWaitSpinner:
    _frames = ("-", "/", "|", "\\")

    def __init__(
        self,
        stream: TextIO | None = None,
        interval: float = 0.1,
    ):
        self.stream = sys.stderr if stream is None else stream
        self.interval = interval

    @contextmanager
    def spin(self, message: str) -> Iterator[None]:
        if not self._should_show():
            yield
            return

        stop_event = Event()
        line_length = len(self._format_line(0, message))
        if not self._write_line(self._format_line(0, message)):
            yield
            return

        def update() -> None:
            frame_index = 1
            while not stop_event.wait(self.interval):
                line = self._format_line(frame_index, message)
                if not self._write_line(line):
                    stop_event.set()
                    return
                frame_index += 1

        thread = Thread(target=update, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop_event.set()
            thread.join()
            self._clear_line(line_length)

    def _should_show(self) -> bool:
        isatty = getattr(self.stream, "isatty", None)
        return callable(isatty) and isatty() and self.interval > 0

    def _format_line(self, frame_index: int, message: str) -> str:
        return f"{self._frames[frame_index % len(self._frames)]} {message}"

    def _write_line(self, line: str) -> bool:
        try:
            self.stream.write(f"\r{line}")
            self.stream.flush()
        except (OSError, ValueError):
            return False
        return True

    def _clear_line(self, line_length: int) -> None:
        try:
            self.stream.write(f"\r{' ' * line_length}\r")
            self.stream.flush()
        except (OSError, ValueError):
            return


def _iter_prefetched_chunks(
    chunks: Iterable[PdfDocumentChunk],
    prefetch_chunks: int,
) -> Iterator[PdfDocumentChunk]:
    if prefetch_chunks <= 0:
        yield from chunks
        return

    iterator = iter(chunks)
    executor = ThreadPoolExecutor(max_workers=1)
    futures: deque[Future[PdfDocumentChunk]] = deque()

    def fill_prefetch_queue() -> None:
        while len(futures) < prefetch_chunks:
            futures.append(executor.submit(next, iterator))

    try:
        futures.append(executor.submit(next, iterator))
        while futures:
            future = futures.popleft()
            try:
                chunk = future.result()
            except StopIteration:
                break
            fill_prefetch_queue()
            yield chunk
    finally:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        _release_future_chunk_images(futures)

        close = getattr(iterator, "close", None)
        if close is not None:
            close()


def _release_future_chunk_images(futures: Iterable[Future[PdfDocumentChunk]]) -> None:
    for future in futures:
        if future.cancelled() or not future.done():
            continue
        try:
            chunk = future.result()
        except Exception:
            continue
        _release_page_images(chunk.pages)
