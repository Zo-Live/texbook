"""Base classes for PDF extraction pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class ContentBlock:
    """A single block of extracted content."""

    text: str
    block_type: str = "text"  # text, heading, definition, theorem, proof, example
    level: int = 0  # 0 = body, 1 = section, 2 = subsection


@dataclass
class ExtractedContent:
    """Complete content extracted from one PDF."""

    source_file: Path
    title: str
    blocks: List[ContentBlock] = field(default_factory=list)


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
