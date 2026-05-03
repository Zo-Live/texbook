"""Text-layer PDF extractor using pymupdf."""

import base64
from pathlib import Path
from typing import Iterable, List, Optional, Sequence
import unicodedata

import pymupdf

from .base import (
    BaseExtractor,
    ContentBlock,
    ExtractedContent,
    ImageRenderOptions,
    PdfDocumentChunk,
    PageTextBlock,
    PdfDocumentContext,
    PdfPageContext,
)


class TextExtractor(BaseExtractor):
    """Extracts content from the text layer of a PDF.

    Uses pymupdf to read text blocks with font size metadata.
    Section headers are identified by font size deltas.
    """

    def extract(self, pdf_path: Path) -> ExtractedContent:
        doc = pymupdf.open(pdf_path)
        title = pdf_path.stem
        blocks: List[ContentBlock] = []

        for page in doc:
            for text_block in self._extract_page_text_blocks(page):
                blocks.append(
                    ContentBlock(
                        text=text_block.text,
                        block_type=text_block.block_type,
                        level=1 if text_block.block_type == "heading" else 0,
                        page_number=page.number + 1,
                        bbox=text_block.bbox,
                        font_size=text_block.font_size,
                    )
                )

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

        doc = pymupdf.open(pdf_path)
        try:
            page_numbers = self._selected_page_numbers(doc.page_count, pages)
            total_chunks = (len(page_numbers) + chunk_size - 1) // chunk_size
            chunk_pages: List[PdfPageContext] = []
            chunk_index = 0

            for page_number in page_numbers:
                page = doc[page_number - 1]
                chunk_pages.append(
                    self._extract_page_context(
                        page,
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
        image_options: ImageRenderOptions,
        include_images: bool,
    ) -> PdfPageContext:
        image_base64 = None
        image_mime_type = "image/png"
        if include_images:
            render_dpi, image_format = self._resolve_image_render(page, image_options)
            image_base64 = self._render_page_base64(
                page,
                render_dpi,
                image_format=image_format,
                jpeg_quality=image_options.jpeg_quality,
            )
            image_mime_type = self._image_mime_type(image_format)

        rect = page.rect
        return PdfPageContext(
            page_number=page.number + 1,
            width=rect.width,
            height=rect.height,
            text_blocks=self._extract_page_text_blocks(page),
            image_base64=image_base64,
            image_mime_type=image_mime_type,
        )

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
