"""Base classes for PDF extraction pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class ContentBlock:
    """A single block of extracted content."""

    text: str
    block_type: str = "text"  # text, heading, definition, theorem, proof, example
    level: int = 0  # 0 = body, 1 = section, 2 = subsection
    page_number: Optional[int] = None
    bbox: Optional[Tuple[float, float, float, float]] = None
    font_size: Optional[float] = None


@dataclass
class ExtractedContent:
    """Complete content extracted from one PDF."""

    source_file: Path
    title: str
    blocks: List[ContentBlock] = field(default_factory=list)


@dataclass
class PageTextBlock:
    """A positioned text block on one PDF page."""

    text: str
    bbox: Tuple[float, float, float, float]
    font_size: float
    block_type: str = "text"


@dataclass
class PdfPageContext:
    """All LLM-facing context for one PDF page."""

    page_number: int
    width: float
    height: float
    text_blocks: List[PageTextBlock] = field(default_factory=list)
    image_base64: Optional[str] = None
    image_mime_type: str = "image/png"

    @property
    def plain_text(self) -> str:
        return "\n".join(block.text for block in self.text_blocks if block.text)


@dataclass
class PdfDocumentContext:
    """Page-level PDF context used by the LLM conversion pipeline."""

    source_file: Path
    title: str
    pages: List[PdfPageContext] = field(default_factory=list)


@dataclass
class PdfDocumentChunk:
    """A chunk of page-level PDF context for one LLM request."""

    source_file: Path
    title: str
    chunk_index: int
    total_chunks: int
    pages: List[PdfPageContext] = field(default_factory=list)


@dataclass
class ImageRenderOptions:
    """Options for rendering PDF pages to LLM-facing images."""

    dpi: int = 160
    dpi_min: int = 100
    dpi_max: int = 160
    image_format: str = "png"
    jpeg_quality: int = 85

    def __post_init__(self) -> None:
        if self.dpi <= 0:
            raise ValueError("image dpi must be positive.")
        if self.dpi_min <= 0:
            raise ValueError("image dpi min must be positive.")
        if self.dpi_max <= 0:
            raise ValueError("image dpi max must be positive.")
        if self.dpi_min > self.dpi_max:
            raise ValueError("image dpi min must be less than or equal to image dpi max.")
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError("jpeg quality must be between 1 and 100.")

        normalized_format = self.image_format.lower()
        if normalized_format == "jpg":
            normalized_format = "jpeg"
        if normalized_format not in {"png", "jpeg", "auto"}:
            raise ValueError("image format must be png, jpeg, jpg, or auto.")
        self.image_format = normalized_format


class BaseExtractor(ABC):
    """Abstract base for all PDF extractors.

    Subclasses implement different extraction strategies:
    - TextExtractor: reads text layer via pymupdf
    - (future) ImageExtractor, FormulaExtractor
    """

    @abstractmethod
    def extract(self, pdf_path: Path) -> ExtractedContent:
        """Extract structured content from a PDF file."""
        ...
