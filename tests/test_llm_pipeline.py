"""Tests for the LLM PDF conversion pipeline."""

from pathlib import Path

import pytest

from latex_tools.extract.base import (
    ImageRenderOptions,
    PageTextBlock,
    PdfDocumentChunk,
    PdfPageContext,
)
from latex_tools.llm.pipeline import LLMPdfConverter, _append_tail, _tail


class FakeExtractor:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []
        self.chunks = []

    def extract_context(self, pdf_path, pages=None, image_dpi=160, include_images=True):
        raise AssertionError("LLMPdfConverter should use iter_context_chunks.")

    def iter_context_chunks(
        self,
        pdf_path,
        *,
        pages=None,
        image_dpi=160,
        include_images=True,
        image_options=None,
        chunk_size=4,
    ):
        self.calls.append(
            {
                "pdf_path": pdf_path,
                "pages": pages,
                "image_dpi": image_dpi,
                "include_images": include_images,
                "image_options": image_options,
                "chunk_size": chunk_size,
            }
        )
        wanted_pages = set(pages) if pages is not None else None
        selected_pages = [
            page
            for page in self.pages
            if wanted_pages is None or page.page_number in wanted_pages
        ]
        total_chunks = (len(selected_pages) + chunk_size - 1) // chunk_size

        for offset in range(0, len(selected_pages), chunk_size):
            chunk = PdfDocumentChunk(
                source_file=pdf_path,
                title=pdf_path.stem,
                chunk_index=offset // chunk_size + 1,
                total_chunks=total_chunks,
                pages=list(selected_pages[offset : offset + chunk_size]),
            )
            self.chunks.append(chunk)
            yield chunk


class FakeClient:
    def __init__(self, latex_fragments=None):
        self.calls = []
        self.latex_fragments = latex_fragments

    def generate_latex_chunk(
        self,
        *,
        document_title,
        pages,
        chunk_index,
        total_chunks,
        previous_latex_tail="",
        extra_prompt="",
    ):
        self.calls.append(
            {
                "document_title": document_title,
                "pages": [page.page_number for page in pages],
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "previous_latex_tail": previous_latex_tail,
                "extra_prompt": extra_prompt,
            }
        )
        latex = (
            self.latex_fragments[chunk_index - 1]
            if self.latex_fragments is not None
            else f"\\section{{Chunk {chunk_index}}}"
        )
        return type(
            "Result",
            (),
            {
                "latex": latex,
                "notes": [f"chunk-{chunk_index}"],
            },
        )()


class RaisingClient:
    def generate_latex_chunk(self, **kwargs):
        raise RuntimeError("LLM failed")


def test_pipeline_chunks_pages_and_builds_document():
    pages = [
        PdfPageContext(
            page_number=1,
            width=1,
            height=1,
            text_blocks=[
                PageTextBlock(
                    text="第一页",
                    bbox=(0, 0, 1, 1),
                    font_size=12,
                )
            ],
            image_base64="aGVsbG8=",
        ),
        PdfPageContext(
            page_number=2,
            width=1,
            height=1,
            text_blocks=[
                PageTextBlock(
                    text="第二页",
                    bbox=(0, 0, 1, 1),
                    font_size=12,
                )
            ],
            image_base64="aGVsbG8=",
        ),
        PdfPageContext(
            page_number=3,
            width=1,
            height=1,
            text_blocks=[
                PageTextBlock(
                    text="第三页",
                    bbox=(0, 0, 1, 1),
                    font_size=12,
                )
            ],
            image_base64="aGVsbG8=",
        ),
    ]
    extractor = FakeExtractor(pages)
    client = FakeClient()
    converter = LLMPdfConverter(client, extractor=extractor, chunk_pages=2, image_dpi=144)

    result = converter.convert(Path("docs/sample.pdf"))

    assert "\\documentclass[UTF8]{ctexart}" in result.latex
    assert "\\section{Chunk 1}" in result.latex
    assert "\\section{Chunk 2}" in result.latex
    assert result.notes == ["chunk-1", "chunk-2"]
    assert extractor.calls[0]["image_dpi"] == 144
    assert extractor.calls[0]["chunk_size"] == 2
    assert extractor.calls[0]["image_options"].dpi == 144
    assert extractor.calls[0]["image_options"].image_format == "png"
    assert client.calls[0]["pages"] == [1, 2]
    assert client.calls[1]["pages"] == [3]
    assert client.calls[1]["previous_latex_tail"]
    assert all(page.image_base64 is None for chunk in extractor.chunks for page in chunk.pages)


def test_append_tail_matches_tail_of_joined_fragments():
    fragments = [
        "a" * 8,
        "b" * 8,
        "c" * 8,
    ]
    previous_latex_tail = ""

    for index, fragment in enumerate(fragments):
        previous_latex_tail = _append_tail(
            previous_latex_tail,
            fragment,
            has_previous_fragment=index > 0,
            max_chars=12,
        )
        assert previous_latex_tail == _tail("\n\n".join(fragments[: index + 1]), 12)


def test_pipeline_passes_incremental_tail_to_later_chunks():
    pages = [
        PdfPageContext(page_number=1, width=1, height=1),
        PdfPageContext(page_number=2, width=1, height=1),
        PdfPageContext(page_number=3, width=1, height=1),
    ]
    fragments = [
        "first-fragment",
        "second-fragment",
        "third-fragment",
    ]
    extractor = FakeExtractor(pages)
    client = FakeClient(latex_fragments=fragments)
    converter = LLMPdfConverter(client, extractor=extractor, chunk_pages=1)

    converter.convert(Path("docs/sample.pdf"))

    assert client.calls[0]["previous_latex_tail"] == ""
    assert client.calls[1]["previous_latex_tail"] == _tail(fragments[0])
    assert client.calls[2]["previous_latex_tail"] == _tail("\n\n".join(fragments[:2]))


def test_pipeline_raises_when_stream_selects_no_pages():
    extractor = FakeExtractor([])
    client = FakeClient()
    converter = LLMPdfConverter(client, extractor=extractor, chunk_pages=2)

    with pytest.raises(ValueError, match="No pages were selected"):
        converter.convert(Path("docs/sample.pdf"))

    assert client.calls == []


def test_pipeline_releases_chunk_images_when_client_fails():
    pages = [
        PdfPageContext(page_number=1, width=1, height=1, image_base64="aGVsbG8="),
    ]
    extractor = FakeExtractor(pages)
    converter = LLMPdfConverter(RaisingClient(), extractor=extractor, chunk_pages=1)

    with pytest.raises(RuntimeError, match="LLM failed"):
        converter.convert(Path("docs/sample.pdf"))

    assert extractor.chunks[0].pages[0].image_base64 is None


def test_pipeline_uses_custom_image_options():
    pages = [PdfPageContext(page_number=1, width=1, height=1)]
    image_options = ImageRenderOptions(
        dpi=120,
        dpi_min=90,
        dpi_max=180,
        image_format="auto",
        jpeg_quality=92,
    )
    extractor = FakeExtractor(pages)
    client = FakeClient()
    converter = LLMPdfConverter(
        client,
        extractor=extractor,
        chunk_pages=1,
        image_dpi=120,
        image_options=image_options,
    )

    converter.convert(Path("docs/sample.pdf"))

    assert extractor.calls[0]["image_options"] is image_options
