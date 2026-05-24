"""Tests for text-layer page context extraction."""

from pathlib import Path
import base64

import pymupdf
import pytest

from texbook.extract.base import (
    DocumentExtractionError,
    ImageRenderOptions,
    PageTextBlock,
)
from texbook.extract.text_extractor import TextExtractor


def _write_blank_pdf(path: Path, page_count: int) -> None:
    doc = pymupdf.open()
    try:
        for _ in range(page_count):
            doc.new_page()
        doc.save(path)
    finally:
        doc.close()


def _write_encrypted_pdf(path: Path) -> None:
    doc = pymupdf.open()
    try:
        doc.new_page()
        doc.save(
            path,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw="user",
            permissions=0,
        )
    finally:
        doc.close()


def test_extract_context_wraps_empty_file_errors(tmp_path):
    empty_path = tmp_path / "empty.pdf"
    empty_path.write_bytes(b"")

    with pytest.raises(DocumentExtractionError, match="empty file"):
        TextExtractor().extract_context(empty_path)


def test_extract_context_wraps_damaged_file_errors(tmp_path):
    damaged_path = tmp_path / "damaged.pdf"
    damaged_path.write_bytes(b"not a pdf")

    with pytest.raises(DocumentExtractionError, match="unsupported or damaged"):
        TextExtractor().extract_context(damaged_path)


def test_extract_context_wraps_encrypted_file_errors(tmp_path):
    locked_path = tmp_path / "locked.pdf"
    _write_encrypted_pdf(locked_path)

    with pytest.raises(DocumentExtractionError, match="encrypted"):
        TextExtractor().extract_context(locked_path)


def test_extract_context_allows_pymupdf_supported_non_pdf_files(tmp_path):
    text_path = tmp_path / "notes.txt"
    text_path.write_text("hello", encoding="utf-8")

    context = TextExtractor().extract_context(text_path, include_images=False)

    assert context.title == "notes"
    assert [page.page_number for page in context.pages] == [1]
    assert context.pages[0].image_base64 is None


def test_iter_context_chunks_renders_only_selected_pages(tmp_path, monkeypatch):
    pdf_path = tmp_path / "sample.pdf"
    _write_blank_pdf(pdf_path, page_count=5)
    rendered_pages = []

    def fake_render(self, page, image_dpi, *, image_format="png", jpeg_quality=85):
        rendered_pages.append(page.number + 1)
        return f"image-{page.number + 1}-{image_dpi}"

    def fake_text_blocks(self, page):
        return [
            PageTextBlock(
                text=f"page-{page.number + 1}",
                bbox=(0, 0, 1, 1),
                font_size=12,
            )
        ]

    monkeypatch.setattr(TextExtractor, "_render_page_base64", fake_render)
    monkeypatch.setattr(TextExtractor, "_extract_page_text_blocks", fake_text_blocks)

    extractor = TextExtractor()
    chunks = list(
        extractor.iter_context_chunks(
            pdf_path,
            pages=[5, 2, 99],
            image_dpi=144,
            include_images=True,
            chunk_size=1,
        )
    )

    assert rendered_pages == [2, 5]
    assert [chunk.chunk_index for chunk in chunks] == [1, 2]
    assert [chunk.total_chunks for chunk in chunks] == [2, 2]
    assert [[page.page_number for page in chunk.pages] for chunk in chunks] == [[2], [5]]
    assert chunks[0].pages[0].image_base64 == "image-2-144"
    assert chunks[1].pages[0].text_blocks[0].text == "page-5"


def test_extract_context_supports_png_and_jpeg_rendering(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _write_blank_pdf(pdf_path, page_count=1)
    extractor = TextExtractor()

    png_context = extractor.extract_context(
        pdf_path,
        pages=[1],
        image_options=ImageRenderOptions(dpi=30, image_format="png"),
    )
    jpeg_context = extractor.extract_context(
        pdf_path,
        pages=[1],
        image_options=ImageRenderOptions(dpi=30, image_format="jpeg"),
    )

    png_bytes = base64.b64decode(png_context.pages[0].image_base64)
    jpeg_bytes = base64.b64decode(jpeg_context.pages[0].image_base64)

    assert png_context.pages[0].image_mime_type == "image/png"
    assert jpeg_context.pages[0].image_mime_type == "image/jpeg"
    assert png_bytes.startswith(b"\x89PNG")
    assert jpeg_bytes.startswith(b"\xff\xd8")


def test_extract_context_keeps_existing_page_selection_behavior(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _write_blank_pdf(pdf_path, page_count=4)

    context = TextExtractor().extract_context(
        pdf_path,
        pages=[3, 1, 3, 99],
        include_images=False,
    )

    assert context.title == "sample"
    assert [page.page_number for page in context.pages] == [1, 3]
    assert all(page.image_base64 is None for page in context.pages)


def test_auto_image_render_strategy_prefers_format_by_page_content():
    extractor = TextExtractor()

    class FakePage:
        def __init__(self, images=None, drawings=None):
            self._images = images or []
            self._drawings = drawings or []

        def get_images(self, full=False):
            assert full is True
            return self._images

        def get_drawings(self):
            return self._drawings

    options = ImageRenderOptions(dpi_min=90, dpi_max=180, image_format="auto")

    assert extractor._resolve_image_render(FakePage(), options) == (90, "png")
    assert extractor._resolve_image_render(FakePage(images=[1]), options) == (180, "jpeg")
    assert extractor._resolve_image_render(FakePage(drawings=[1]), options) == (180, "png")
