"""LLM-driven PDF to LaTeX conversion pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence

from ..convert.latex_converter import LatexConverter
from ..extract.base import ImageRenderOptions, PdfPageContext
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
        image_options: ImageRenderOptions | None = None,
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
        self.image_options = image_options or ImageRenderOptions(
            dpi=image_dpi,
            dpi_max=image_dpi,
        )
        self.extra_prompt = extra_prompt
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

        for chunk in self.extractor.iter_context_chunks(
            pdf_path,
            pages=pages,
            image_dpi=self.image_dpi,
            include_images=True,
            image_options=self.image_options,
            chunk_size=self.chunk_pages,
        ):
            if not saw_chunk:
                document_title = chunk.title
            saw_chunk = True
            try:
                result = self.client.generate_latex_chunk(
                    document_title=chunk.title,
                    pages=chunk.pages,
                    chunk_index=chunk.chunk_index,
                    total_chunks=chunk.total_chunks,
                    previous_latex_tail=previous_latex_tail,
                    extra_prompt=self.extra_prompt,
                )
            finally:
                _release_page_images(chunk.pages)

            previous_latex_tail = _append_tail(
                previous_latex_tail,
                result.latex,
                has_previous_fragment=bool(fragments),
            )
            fragments.append(result.latex)
            notes.extend(result.notes)

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
