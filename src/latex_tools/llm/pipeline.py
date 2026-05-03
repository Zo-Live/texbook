"""LLM-driven PDF to LaTeX conversion pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence

from ..convert.latex_converter import LatexConverter
from ..extract.base import PdfPageContext
from ..extract.text_extractor import TextExtractor
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
        extra_prompt: str = "",
    ):
        if chunk_pages <= 0:
            raise ValueError("chunk_pages must be positive.")
        if image_dpi <= 0:
            raise ValueError("image_dpi must be positive.")

        self.client = client
        self.extractor = extractor or TextExtractor()
        self.chunk_pages = chunk_pages
        self.image_dpi = image_dpi
        self.extra_prompt = extra_prompt
        self.document_builder = LatexConverter()

    def convert(
        self,
        pdf_path: Path,
        *,
        pages: Sequence[int] | None = None,
    ) -> LLMConversionResult:
        context = self.extractor.extract_context(
            pdf_path,
            pages=pages,
            image_dpi=self.image_dpi,
            include_images=True,
        )
        if not context.pages:
            raise ValueError("No pages were selected for conversion.")

        chunks = list(_chunk_pages(context.pages, self.chunk_pages))
        fragments: list[str] = []
        notes: list[str] = []
        previous_latex_tail = ""

        for index, page_chunk in enumerate(chunks, start=1):
            result = self.client.generate_latex_chunk(
                document_title=context.title,
                pages=page_chunk,
                chunk_index=index,
                total_chunks=len(chunks),
                previous_latex_tail=previous_latex_tail,
                extra_prompt=self.extra_prompt,
            )
            fragments.append(result.latex)
            notes.extend(result.notes)
            previous_latex_tail = _tail("\n\n".join(fragments))

        return LLMConversionResult(
            latex=self.document_builder.convert_fragments(
                title=context.title,
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
