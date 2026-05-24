"""Text-layer PDF extractor using pymupdf."""

import base64
from pathlib import Path
from typing import Iterable, List, Optional, Sequence
import unicodedata

import pymupdf

from .base import (
    BaseExtractor,
    ContentBlock,
    DocumentExtractionError,
    DocumentOpenError,
    DocumentReadError,
    ExtractedContent,
    ImageRenderOptions,
    PdfDocumentChunk,
    PageTextBlock,
    PdfDocumentContext,
    PdfPageContext,
)
from ..structure import BookmarkEntry, PageHeadingCandidate, StructureEvidence


_PYMUPDF_OPEN_ERRORS = tuple(
    exc_type
    for exc_type in (
        getattr(pymupdf, "EmptyFileError", None),
        getattr(pymupdf, "FileDataError", None),
        getattr(pymupdf, "FileNotFoundError", None),
    )
    if isinstance(exc_type, type)
)


class TextExtractor(BaseExtractor):
    """Extracts content from the text layer of a PDF.

    Uses pymupdf to read text blocks with font size metadata.
    Section headers are identified by font size deltas.
    """

    def extract(self, pdf_path: Path) -> ExtractedContent:
        title = pdf_path.stem
        blocks: List[ContentBlock] = []
        doc = self._open_document(pdf_path)

        try:
            for page_number in range(1, self._page_count(doc, pdf_path) + 1):
                page = self._load_page(doc, pdf_path, page_number)
                for text_block in self._read_page_text_blocks(
                    page,
                    pdf_path=pdf_path,
                    page_number=page_number,
                ):
                    blocks.append(
                        ContentBlock(
                            text=text_block.text,
                            block_type=text_block.block_type,
                            level=1 if text_block.block_type == "heading" else 0,
                            page_number=page_number,
                            bbox=text_block.bbox,
                            font_size=text_block.font_size,
                        )
                    )
        finally:
            doc.close()
        return ExtractedContent(source_file=pdf_path, title=title, blocks=blocks)

    def extract_context(
        self,
        pdf_path: Path,
        pages: Optional[Sequence[int]] = None,
        image_dpi: int = 160,
        include_images: bool = True,
        image_options: ImageRenderOptions | None = None,
    ) -> PdfDocumentContext:
        """Extract page-level context for the LLM conversion pipeline.

        Page numbers are 1-based. If ``pages`` is not provided, every PDF page is
        extracted.
        """
        page_contexts: List[PdfPageContext] = []
        for chunk in self.iter_context_chunks(
            pdf_path,
            pages=pages,
            image_dpi=image_dpi,
            include_images=include_images,
            image_options=image_options,
            chunk_size=1,
        ):
            page_contexts.extend(chunk.pages)
        return PdfDocumentContext(
            source_file=pdf_path,
            title=pdf_path.stem,
            pages=page_contexts,
        )

    def iter_context_chunks(
        self,
        pdf_path: Path,
        *,
        pages: Optional[Sequence[int]] = None,
        image_dpi: int = 160,
        include_images: bool = True,
        image_options: ImageRenderOptions | None = None,
        chunk_size: int = 4,
    ) -> Iterable[PdfDocumentChunk]:
        """Yield page-level context in chunks for the LLM conversion pipeline."""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        resolved_image_options = self._resolve_image_options(image_dpi, image_options)

        doc = self._open_document(pdf_path)
        try:
            page_numbers = self._selected_page_numbers(
                self._page_count(doc, pdf_path),
                pages,
            )
            total_chunks = (len(page_numbers) + chunk_size - 1) // chunk_size
            chunk_pages: List[PdfPageContext] = []
            chunk_index = 0

            for page_number in page_numbers:
                page = self._load_page(doc, pdf_path, page_number)
                chunk_pages.append(
                    self._extract_page_context(
                        page,
                        pdf_path=pdf_path,
                        page_number=page_number,
                        image_options=resolved_image_options,
                        include_images=include_images,
                    )
                )

                if len(chunk_pages) == chunk_size:
                    chunk_index += 1
                    yield PdfDocumentChunk(
                        source_file=pdf_path,
                        title=pdf_path.stem,
                        chunk_index=chunk_index,
                        total_chunks=total_chunks,
                        pages=chunk_pages,
                    )
                    chunk_pages = []

            if chunk_pages:
                chunk_index += 1
                yield PdfDocumentChunk(
                    source_file=pdf_path,
                    title=pdf_path.stem,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                    pages=chunk_pages,
                )
        finally:
            doc.close()

    def extract_structure_evidence(
        self,
        pdf_path: Path,
        *,
        pages: Optional[Sequence[int]] = None,
    ) -> StructureEvidence:
        """Extract text-only structure evidence for planning."""
        doc = self._open_document(pdf_path)
        try:
            page_count = self._page_count(doc, pdf_path)
            page_numbers = self._selected_page_numbers(page_count, pages)
            selected_set = set(page_numbers)
            bookmarks = self._read_bookmarks(doc, selected_set=selected_set)
            heading_candidates: list[PageHeadingCandidate] = []
            page_starts: dict[int, str] = {}

            for page_number in page_numbers:
                page = self._load_page(doc, pdf_path, page_number)
                blocks = self._read_page_text_blocks(
                    page,
                    pdf_path=pdf_path,
                    page_number=page_number,
                )
                page_text = " ".join(block.text for block in blocks if block.text)
                if page_text:
                    page_starts[page_number] = page_text[:300]
                heading_candidates.extend(
                    self._heading_candidates_from_blocks(
                        blocks,
                        page_number=page_number,
                    )
                )

            return StructureEvidence(
                source_title=pdf_path.stem,
                total_pages=page_count,
                selected_pages=page_numbers,
                bookmarks=bookmarks,
                heading_candidates=heading_candidates,
                page_starts=page_starts,
            )
        finally:
            doc.close()

    def _selected_page_numbers(
        self,
        page_count: int,
        pages: Optional[Sequence[int]],
    ) -> List[int]:
        wanted_pages = set(pages) if pages is not None else None
        return [
            page_number
            for page_number in range(1, page_count + 1)
            if wanted_pages is None or page_number in wanted_pages
        ]

    def _extract_page_context(
        self,
        page: pymupdf.Page,
        *,
        pdf_path: Path,
        page_number: int,
        image_options: ImageRenderOptions,
        include_images: bool,
    ) -> PdfPageContext:
        image_base64 = None
        image_mime_type = "image/png"
        if include_images:
            try:
                render_dpi, image_format = self._resolve_image_render(
                    page,
                    image_options,
                )
                image_base64 = self._render_page_base64(
                    page,
                    render_dpi,
                    image_format=image_format,
                    jpeg_quality=image_options.jpeg_quality,
                )
            except DocumentExtractionError:
                raise
            except (OSError, RuntimeError, ValueError) as exc:
                raise DocumentReadError(
                    f"Cannot render page {page_number}: {_describe_pymupdf_error(exc)}",
                    source_file=pdf_path,
                    page_number=page_number,
                ) from exc
            image_mime_type = self._image_mime_type(image_format)

        try:
            rect = page.rect
        except (OSError, RuntimeError, ValueError) as exc:
            raise DocumentReadError(
                f"Cannot read page {page_number}: {_describe_pymupdf_error(exc)}",
                source_file=pdf_path,
                page_number=page_number,
            ) from exc
        return PdfPageContext(
            page_number=page_number,
            width=rect.width,
            height=rect.height,
            text_blocks=self._read_page_text_blocks(
                page,
                pdf_path=pdf_path,
                page_number=page_number,
            ),
            image_base64=image_base64,
            image_mime_type=image_mime_type,
        )

    def _open_document(self, pdf_path: Path) -> pymupdf.Document:
        try:
            doc = pymupdf.open(pdf_path)
        except _PYMUPDF_OPEN_ERRORS as exc:
            raise DocumentOpenError(
                f"Cannot open document: {_describe_pymupdf_error(exc)}",
                source_file=pdf_path,
            ) from exc
        except (OSError, RuntimeError, ValueError) as exc:
            raise DocumentOpenError(
                f"Cannot open document: {_describe_pymupdf_error(exc)}",
                source_file=pdf_path,
            ) from exc

        try:
            needs_pass = getattr(doc, "needs_pass", False)
            if callable(needs_pass):
                needs_pass = needs_pass()
            if needs_pass:
                raise DocumentOpenError(
                    "Cannot open document: encrypted document requires a password.",
                    source_file=pdf_path,
                )
        except DocumentOpenError:
            doc.close()
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            doc.close()
            raise DocumentOpenError(
                f"Cannot initialize document: {_describe_pymupdf_error(exc)}",
                source_file=pdf_path,
            ) from exc

        return doc

    def _page_count(self, doc: pymupdf.Document, pdf_path: Path) -> int:
        try:
            return int(doc.page_count)
        except (OSError, RuntimeError, ValueError) as exc:
            raise DocumentReadError(
                f"Cannot read document page count: {_describe_pymupdf_error(exc)}",
                source_file=pdf_path,
            ) from exc

    def _load_page(
        self,
        doc: pymupdf.Document,
        pdf_path: Path,
        page_number: int,
    ) -> pymupdf.Page:
        try:
            return doc[page_number - 1]
        except (OSError, RuntimeError, ValueError) as exc:
            raise DocumentReadError(
                f"Cannot read page {page_number}: {_describe_pymupdf_error(exc)}",
                source_file=pdf_path,
                page_number=page_number,
            ) from exc

    def _read_page_text_blocks(
        self,
        page: pymupdf.Page,
        *,
        pdf_path: Path,
        page_number: int,
    ) -> List[PageTextBlock]:
        try:
            return self._extract_page_text_blocks(page)
        except DocumentExtractionError:
            raise
        except (OSError, RuntimeError, ValueError) as exc:
            raise DocumentReadError(
                f"Cannot read text on page {page_number}: {_describe_pymupdf_error(exc)}",
                source_file=pdf_path,
                page_number=page_number,
            ) from exc

    def _resolve_image_options(
        self,
        image_dpi: int,
        image_options: ImageRenderOptions | None,
    ) -> ImageRenderOptions:
        if image_options is not None:
            return image_options
        return ImageRenderOptions(dpi=image_dpi, dpi_max=image_dpi)

    def _resolve_image_render(
        self,
        page: pymupdf.Page,
        image_options: ImageRenderOptions,
    ) -> tuple[int, str]:
        if image_options.image_format in {"png", "jpeg"}:
            return image_options.dpi, image_options.image_format

        if page.get_images(full=True):
            return image_options.dpi_max, "jpeg"
        if page.get_drawings():
            return image_options.dpi_max, "png"
        return image_options.dpi_min, "png"

    def _extract_page_text_blocks(self, page: pymupdf.Page) -> List[PageTextBlock]:
        text_dict = page.get_text("dict")
        blocks: List[PageTextBlock] = []

        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = self._join_spans(spans)
                if not text:
                    continue
                font_size = self._max_font_size(spans)
                block_type = self._classify_block(text, font_size)
                bbox = tuple(float(value) for value in line.get("bbox", (0, 0, 0, 0)))
                blocks.append(
                    PageTextBlock(
                        text=text,
                        bbox=bbox,
                        font_size=font_size,
                        block_type=block_type,
                    )
                )

        return blocks

    def _read_bookmarks(
        self,
        doc: pymupdf.Document,
        *,
        selected_set: set[int],
    ) -> list[BookmarkEntry]:
        try:
            raw_toc = doc.get_toc(simple=True)
        except (OSError, RuntimeError, ValueError):
            return []

        bookmarks: list[BookmarkEntry] = []
        for item in raw_toc:
            if len(item) < 3:
                continue
            try:
                level = int(item[0])
                title = self._clean_text(str(item[1]))
                page_number = int(item[2])
            except (TypeError, ValueError):
                continue
            if page_number <= 0 or page_number not in selected_set:
                continue
            title = " ".join(title.split())
            if not title:
                continue
            bookmarks.append(
                BookmarkEntry(
                    level=level,
                    title=title,
                    page_number=page_number,
                )
            )
        return bookmarks

    def _heading_candidates_from_blocks(
        self,
        blocks: Sequence[PageTextBlock],
        *,
        page_number: int,
    ) -> list[PageHeadingCandidate]:
        if not blocks:
            return []
        font_sizes = sorted({block.font_size for block in blocks}, reverse=True)
        high_size_threshold = font_sizes[min(2, len(font_sizes) - 1)] if font_sizes else 14
        candidates: list[PageHeadingCandidate] = []
        seen: set[str] = set()
        for block in blocks:
            text = " ".join(block.text.split())
            if not text or len(text) > 120 or text in seen:
                continue
            if block.block_type == "heading" or block.font_size >= high_size_threshold:
                candidates.append(
                    PageHeadingCandidate(
                        page_number=page_number,
                        text=text,
                        font_size=block.font_size,
                        block_type=block.block_type,
                    )
                )
                seen.add(text)
        return candidates

    def _join_spans(self, spans: Iterable[dict]) -> str:
        parts = [self._clean_text(span.get("text", "")) for span in spans]
        text = "".join(parts)
        return " ".join(text.split())

    def _max_font_size(self, spans: Iterable[dict]) -> float:
        sizes = [float(span.get("size", 12)) for span in spans]
        return max(sizes, default=12.0)

    def _render_page_base64(
        self,
        page: pymupdf.Page,
        image_dpi: int,
        *,
        image_format: str = "png",
        jpeg_quality: int = 85,
    ) -> str:
        zoom = image_dpi / 72
        matrix = pymupdf.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return base64.b64encode(
            pixmap.tobytes(image_format, jpg_quality=jpeg_quality)
        ).decode("ascii")

    def _image_mime_type(self, image_format: str) -> str:
        if image_format == "jpeg":
            return "image/jpeg"
        return "image/png"

    def _clean_text(self, text: str) -> str:
        return "".join(
            ch
            for ch in text
            if ch in "\t\n\r" or not unicodedata.category(ch).startswith("C")
        )

    def _classify_block(self, text: str, font_size: float) -> str:
        heading_keywords = ("定义", "定理", "证明", "例", "性质", "推论", "引理")

        if font_size > 14:
            return "heading"

        for kw in heading_keywords:
            if text.startswith(kw):
                return self._map_keyword_to_type(kw)

        return "text"

    def _map_keyword_to_type(self, keyword: str) -> str:
        mapping = {
            "定义": "definition",
            "定理": "theorem",
            "证明": "proof",
            "例": "example",
            "性质": "property",
            "推论": "corollary",
            "引理": "lemma",
        }
        return mapping.get(keyword, "text")


def _describe_pymupdf_error(exc: Exception) -> str:
    if _is_instance(exc, "FileNotFoundError"):
        return "file not found."
    if _is_instance(exc, "EmptyFileError"):
        return "empty file."
    if _is_instance(exc, "FileDataError"):
        return "unsupported or damaged document."
    message = str(exc).strip()
    if "encrypted" in message.lower():
        return "encrypted document requires a password."
    return message or exc.__class__.__name__


def _is_instance(exc: Exception, class_name: str) -> bool:
    exc_type = getattr(pymupdf, class_name, None)
    return isinstance(exc_type, type) and isinstance(exc, exc_type)
