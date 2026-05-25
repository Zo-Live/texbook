"""Core factory for reusable PDF conversion pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..document_class import DocumentClassMode
from ..extract.base import ImageRenderOptions
from ..extract.text_extractor import TextExtractor
from ..output_options import DEFAULT_OUTPUT_OPTIONS, LatexOutputOptions
from ..structure import StructureMode, StructurePlannerOptions
from .cache import ChunkCacheOptions
from .client import OpenAICompatibleClient
from .config import LLMConfig
from .pipeline import LLMPdfConverter, LatexChunkClient
from .presets import PromptPreset
from .scheduler import (
    LLMRateLimiter,
    LLMScheduler,
    ProgressReporter,
    RetryOptions,
)


@dataclass(frozen=True)
class PdfConversionOptions:
    """Core options for building a reusable PDF converter."""

    chunk_pages: int = 4
    image_dpi: int = 160
    image_options: ImageRenderOptions | None = None
    prefetch_chunks: int = 1
    cache_options: ChunkCacheOptions | None = None
    extra_prompt: str = ""
    prompt_preset: PromptPreset | None = None
    title_source: str = "filename"
    manual_title: str | None = None
    show_date: bool = False
    document_class: DocumentClassMode | str = DocumentClassMode.auto
    structure_options: StructurePlannerOptions = field(
        default_factory=lambda: StructurePlannerOptions(mode=StructureMode.auto)
    )
    output_options: LatexOutputOptions = DEFAULT_OUTPUT_OPTIONS
    retry_options: RetryOptions = field(default_factory=RetryOptions)
    llm_max_concurrency: int = 1
    llm_min_request_interval: float = 0.0


def build_pdf_converter(
    config: LLMConfig,
    *,
    options: PdfConversionOptions | None = None,
    client: LatexChunkClient | None = None,
    extractor: TextExtractor | None = None,
    scheduler: LLMScheduler | None = None,
    progress_reporter: ProgressReporter | None = None,
) -> LLMPdfConverter:
    """Build a core converter without depending on CLI adapters."""
    resolved_options = options or PdfConversionOptions()
    llm_client = client or OpenAICompatibleClient(config)
    llm_scheduler = scheduler or LLMScheduler(
        retry_options=resolved_options.retry_options,
        rate_limiter=LLMRateLimiter(
            max_concurrency=resolved_options.llm_max_concurrency,
            min_request_interval=resolved_options.llm_min_request_interval,
        ),
        reporter=progress_reporter,
    )

    return LLMPdfConverter(
        llm_client,
        extractor=extractor,
        chunk_pages=resolved_options.chunk_pages,
        image_dpi=resolved_options.image_dpi,
        image_options=resolved_options.image_options,
        prefetch_chunks=resolved_options.prefetch_chunks,
        cache_options=resolved_options.cache_options,
        extra_prompt=resolved_options.extra_prompt,
        prompt_preset=resolved_options.prompt_preset,
        title_source=resolved_options.title_source,
        manual_title=resolved_options.manual_title,
        show_date=resolved_options.show_date,
        document_class=resolved_options.document_class,
        structure_options=resolved_options.structure_options,
        scheduler=llm_scheduler,
        progress_reporter=progress_reporter,
        output_options=resolved_options.output_options,
    )
