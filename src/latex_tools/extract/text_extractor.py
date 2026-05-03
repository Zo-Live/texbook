"""Text-layer PDF extractor using pymupdf."""

from pathlib import Path
from typing import List
import unicodedata

import pymupdf

from .base import BaseExtractor, ContentBlock, ExtractedContent


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
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = self._clean_text(span.get("text", "")).strip()
                        if not text:
                            continue
                        font_size = span.get("size", 12)
                        block_type = self._classify_block(text, font_size)
                        blocks.append(
                            ContentBlock(
                                text=text,
                                block_type=block_type,
                                level=1 if block_type == "heading" else 0,
                            )
                        )

        doc.close()
        return ExtractedContent(source_file=pdf_path, title=title, blocks=blocks)

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
