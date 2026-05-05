"""LLM-driven PDF to LaTeX conversion pipeline."""

import sys
from collections import deque
from contextlib import contextmanager
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Thread
from typing import Iterable, Iterator, Protocol, Sequence, TextIO

from ..convert.latex_converter import LatexConverter
from ..extract.base import ImageRenderOptions, PdfDocumentChunk, PdfPageContext
from ..extract.text_extractor import TextExtractor
from .cache import ChunkCacheOptions, ChunkCacheRun
from .client import LLMChunkResult


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
    ) -> LLMChunkResult:
        """Generate LaTeX for one page chunk."""


@dataclass
class LLMConversionResult:
    """Complete LLM conversion output."""

    latex: str
    notes: list[str] = field(default_factory=list)


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
        progress_stream: TextIO | None = None,
        progress_interval: float = 0.1,
    ):
        if chunk_pages <= 0:
            raise ValueError("chunk_pages must be positive.")
        if image_dpi <= 0:
            raise ValueError("image_dpi must be positive.")
        if prefetch_chunks < 0:
            raise ValueError("prefetch_chunks must be non-negative.")

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
        self.progress_spinner = _LlmWaitSpinner(progress_stream, progress_interval)
        self.document_builder = LatexConverter()

    def convert(
        self,
        pdf_path: Path,
        *,
        pages: Sequence[int] | None = None,
    ) -> LLMConversionResult:
        fragments: list[str] = []
        notes: list[str] = []
        previous_latex_tail = ""
        document_title = pdf_path.stem
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
                    document_title = chunk.title
                    if self.cache_options is not None:
                        cache_run = ChunkCacheRun(
                            options=self.cache_options,
                            pdf_path=pdf_path,
                            pages=pages,
                            document_title=chunk.title,
                            chunk_pages=self.chunk_pages,
                            image_dpi=self.image_dpi,
                            image_options=self.image_options,
                            extra_prompt=self.extra_prompt,
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
                                document_title=chunk.title,
                                pages=chunk.pages,
                                chunk_index=chunk.chunk_index,
                                total_chunks=chunk.total_chunks,
                                previous_latex_tail=previous_latex_tail,
                                extra_prompt=self.extra_prompt,
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
                fragments.append(result.latex)
                notes.extend(result.notes)
        finally:
            close = getattr(chunk_iterator, "close", None)
            if close is not None:
                close()

        if not saw_chunk:
            raise ValueError("No pages were selected for conversion.")

        return LLMConversionResult(
            latex=self.document_builder.convert_fragments(
                title=document_title,
                fragments=fragments,
                notes=notes,
            ),
            notes=notes,
        )


def _chunk_pages(
    pages: Sequence[PdfPageContext],
    chunk_size: int,
) -> list[list[PdfPageContext]]:
    return [list(pages[index : index + chunk_size]) for index in range(0, len(pages), chunk_size)]


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
