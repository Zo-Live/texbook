"""Adapters from GUI settings to reusable TexBook core objects."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from texbook.document_class import DocumentClassMode
from texbook.extract.base import ImageRenderOptions
from texbook.gui.settings import GuiApiKeySource, GuiConversionSettings, parse_gui_pages
from texbook.llm.cache import ChunkCacheOptions
from texbook.llm.config import LLMConfig, LLMConfigError
from texbook.llm.factory import PdfConversionOptions
from texbook.llm.presets import PromptPresetError, load_prompt_preset
from texbook.llm.scheduler import RetryOptions
from texbook.output_options import BeamerBoxStyle, CtexFontProfile, LatexOutputOptions
from texbook.structure import StructureMode, StructurePlannerOptions


class GuiCoreAdapterError(ValueError):
    """Raised when GUI settings cannot be mapped to core conversion objects."""


@dataclass(frozen=True)
class GuiCoreConversionBundle:
    """Core conversion configuration assembled from GUI settings."""

    llm_config: LLMConfig
    conversion_options: PdfConversionOptions
    pages: list[int] | None


def build_core_conversion_bundle(
    settings: GuiConversionSettings,
    *,
    repo_root: Path | None = None,
) -> GuiCoreConversionBundle:
    """Convert GUI settings into core configuration objects without CLI helpers."""
    root = repo_root or Path.cwd()
    try:
        llm_config = LLMConfig.from_values(
            model=settings.model.strip() or None,
            api_key=_api_key_for_core(settings),
            base_url=settings.base_url.strip() or None,
            temperature=settings.temperature,
            timeout=settings.timeout_seconds,
            max_tokens=settings.max_tokens,
        )
        prompt_preset = load_prompt_preset(settings.prompt_preset, repo_root=root)
        image_options = ImageRenderOptions(
            dpi=settings.image_dpi,
            dpi_min=settings.image_dpi_min,
            dpi_max=settings.image_dpi if settings.image_dpi_max is None else settings.image_dpi_max,
            image_format=settings.image_format,
            jpeg_quality=settings.jpeg_quality,
        )
        cache_options = None
        if settings.cache_enabled:
            cache_options = ChunkCacheOptions(
                cache_dir=Path(settings.cache_directory).expanduser(),
                clear=settings.clear_cache,
                llm_model=llm_config.model,
                llm_base_url=llm_config.base_url,
                llm_temperature=llm_config.temperature,
                llm_max_tokens=llm_config.max_tokens,
            )
        output_options = LatexOutputOptions(
            beamer_box_style=BeamerBoxStyle(settings.beamer_box_style),
            ctex_font_profile=CtexFontProfile(settings.ctex_font_profile),
            beamer_title_page=settings.beamer_title_page,
        )
        pages = parse_gui_pages(settings.pages)
        conversion_options = PdfConversionOptions(
            chunk_pages=settings.chunk_pages,
            image_dpi=settings.image_dpi,
            image_options=image_options,
            prefetch_chunks=settings.prefetch_chunks,
            cache_options=cache_options,
            extra_prompt=settings.extra_prompt,
            prompt_preset=prompt_preset,
            title_source=settings.title_source,
            manual_title=_manual_title_for_core(settings),
            show_date=settings.show_date,
            document_class=DocumentClassMode.from_value(settings.document_class),
            structure_options=StructurePlannerOptions(
                mode=StructureMode(settings.structure_mode),
                chunk_pages=settings.structure_chunk_pages,
                max_pages=settings.structure_max_pages,
            ),
            output_options=output_options,
            retry_options=RetryOptions(
                retries=settings.llm_retries,
                initial_delay=settings.llm_retry_initial_delay,
                max_delay=settings.llm_retry_max_delay,
            ),
            llm_max_concurrency=settings.llm_max_concurrency,
            llm_min_request_interval=settings.llm_min_request_interval,
        )
    except (LLMConfigError, PromptPresetError, ValueError) as exc:
        raise GuiCoreAdapterError(str(exc)) from exc

    return GuiCoreConversionBundle(
        llm_config=llm_config,
        conversion_options=conversion_options,
        pages=pages,
    )


def _manual_title_for_core(settings: GuiConversionSettings) -> str | None:
    title = settings.manual_title.strip()
    if not title:
        return None
    return title


def _api_key_for_core(settings: GuiConversionSettings) -> str | None:
    text = settings.api_key.strip()
    if settings.api_key_source != GuiApiKeySource.environment:
        return text or None
    if not text:
        return None
    resolved = os.environ.get(text)
    if not resolved:
        raise GuiCoreAdapterError(f"API Key 环境变量不存在：{text}。")
    return resolved
