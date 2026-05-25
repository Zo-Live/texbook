"""Tests for reusable core converter construction."""

from pathlib import Path

from texbook.document_class import DocumentClassMode
from texbook.extract.base import ImageRenderOptions, PdfDocumentChunk, PdfPageContext
from texbook.llm.cache import ChunkCacheOptions
from texbook.llm.config import LLMConfig
from texbook.llm.factory import PdfConversionOptions, build_pdf_converter
from texbook.llm.scheduler import LLMScheduler, RetryOptions
from texbook.output_options import BeamerBoxStyle, LatexOutputOptions
from texbook.structure import StructureMode, StructurePlannerOptions


class DummyClient:
    def generate_latex_chunk(self, **kwargs):
        raise AssertionError("Not used in factory construction test")


class DummyExtractor:
    def iter_context_chunks(self, *args, **kwargs):
        yield PdfDocumentChunk(
            source_file=Path("sample.pdf"),
            title="sample",
            chunk_index=1,
            total_chunks=1,
            pages=[PdfPageContext(page_number=1, width=1, height=1)],
        )


def test_build_pdf_converter_uses_core_options(tmp_path):
    config = LLMConfig(
        model="test-model",
        api_key="test-key",
        base_url="https://api.example.test/v1",
        temperature=0.3,
        max_tokens=2048,
    )
    image_options = ImageRenderOptions(
        dpi=144,
        dpi_min=96,
        dpi_max=180,
        image_format="jpg",
        jpeg_quality=90,
    )
    cache_options = ChunkCacheOptions(
        cache_dir=tmp_path / "cache",
        llm_model=config.model,
        llm_base_url=config.base_url,
        llm_temperature=config.temperature,
        llm_max_tokens=config.max_tokens,
    )
    output_options = LatexOutputOptions(beamer_box_style=BeamerBoxStyle.tcolorbox)
    options = PdfConversionOptions(
        chunk_pages=2,
        image_dpi=144,
        image_options=image_options,
        prefetch_chunks=0,
        cache_options=cache_options,
        extra_prompt="额外要求",
        title_source="llm",
        show_date=True,
        document_class=DocumentClassMode.ctexbeamer,
        structure_options=StructurePlannerOptions(
            mode=StructureMode.local,
            chunk_pages=3,
            max_pages=12,
        ),
        output_options=output_options,
        retry_options=RetryOptions(retries=4, initial_delay=0.5, max_delay=4.0),
        llm_max_concurrency=2,
        llm_min_request_interval=0.25,
    )

    converter = build_pdf_converter(
        config,
        options=options,
        client=DummyClient(),
        extractor=DummyExtractor(),
    )

    assert converter.client.__class__ is DummyClient
    assert converter.extractor.__class__ is DummyExtractor
    assert converter.chunk_pages == 2
    assert converter.image_options.image_format == "jpeg"
    assert converter.prefetch_chunks == 0
    assert converter.cache_options is cache_options
    assert converter.extra_prompt == "额外要求"
    assert converter.title_source == "llm"
    assert converter.show_date is True
    assert converter.document_class_mode == DocumentClassMode.ctexbeamer
    assert converter.structure_options.mode == StructureMode.local
    assert converter.output_options is output_options
    assert converter.scheduler.retry_options.retries == 4
    assert converter.scheduler.rate_limiter.max_concurrency == 2
    assert converter.scheduler.rate_limiter.min_request_interval == 0.25


def test_build_pdf_converter_preserves_injected_scheduler():
    config = LLMConfig(model="test-model", api_key="test-key")
    scheduler = LLMScheduler()

    converter = build_pdf_converter(
        config,
        client=DummyClient(),
        scheduler=scheduler,
    )

    assert converter.scheduler is scheduler
