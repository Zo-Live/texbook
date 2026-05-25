"""GUI-only conversion settings state and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from texbook.gui.selection import GuiPathSelectionState


class GuiConversionMode(str, Enum):
    """Conversion modes exposed by the GUI."""

    single_file = "single_file"
    project = "project"
    batch = "batch"


@dataclass(frozen=True)
class GuiConversionSettings:
    """All conversion options currently represented by the GUI panel."""

    path_state: GuiPathSelectionState = field(default_factory=GuiPathSelectionState)
    conversion_mode: GuiConversionMode = GuiConversionMode.single_file
    confirm_overwrite: bool = True
    pages: str = ""
    document_class: str = "auto"
    structure_mode: str = "auto"
    structure_chunk_pages: int = 8
    structure_max_pages: int = 32
    manual_title: str = ""
    title_source: str = "filename"
    show_date: bool = False
    beamer_title_page: bool = True
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    prompt_preset: str = "chinese-math"
    extra_prompt: str = ""
    temperature: float = 1.0
    timeout_seconds: float | None = None
    max_tokens: int = 128000
    cache_enabled: bool = True
    cache_directory: str = "build/.texbook_cache"
    clear_cache: bool = False
    chunk_pages: int = 4
    prefetch_chunks: int = 1
    llm_max_concurrency: int = 1
    llm_min_request_interval: float = 0.0
    batch_workers: int = 1
    image_dpi: int = 160
    image_dpi_min: int = 100
    image_dpi_max: int | None = None
    image_format: str = "png"
    jpeg_quality: int = 85
    llm_retries: int = 2
    llm_retry_initial_delay: float = 2.0
    llm_retry_max_delay: float = 30.0
    beamer_box_style: str = "block"
    ctex_font_profile: str = "default"


def validate_gui_settings(settings: GuiConversionSettings) -> list[str]:
    """Return Chinese validation errors for GUI settings."""
    errors: list[str] = []

    if settings.conversion_mode not in {item.value for item in GuiConversionMode}:
        errors.append("转换模式无效。")
    if settings.document_class not in {
        "auto",
        "article",
        "book",
        "beamer",
        "ctexart",
        "ctexbook",
        "ctexbeamer",
    }:
        errors.append("文档类无效。")
    if settings.structure_mode not in {"auto", "off", "local", "llm"}:
        errors.append("结构规划模式无效。")
    if settings.title_source not in {"filename", "llm"}:
        errors.append("标题来源无效。")
    if settings.image_format not in {"auto", "png", "jpeg"}:
        errors.append("图像格式无效。")
    if settings.beamer_box_style not in {"block", "tcolorbox"}:
        errors.append("Beamer 块样式无效。")
    if settings.ctex_font_profile not in {"default", "local"}:
        errors.append("CTeX 字体配置无效。")
    if _parse_pages(settings.pages) is None and settings.pages.strip():
        errors.append("页面范围格式无效，请使用 1,3-5 这样的 1-based 页码。")
    if settings.manual_title.strip() and settings.title_source == "llm":
        errors.append("手动标题不能与 LLM 标题来源同时使用。")
    if settings.image_dpi_min <= 0:
        errors.append("图片 DPI 下限必须为正数。")
    if settings.image_dpi_max is not None and settings.image_dpi_max <= 0:
        errors.append("图片 DPI 上限必须为正数。")
    if settings.image_dpi_max is not None and settings.image_dpi_min > settings.image_dpi_max:
        errors.append("图片 DPI 下限不能大于上限。")
    if not 1 <= settings.jpeg_quality <= 100:
        errors.append("JPEG 质量必须在 1 到 100 之间。")
    if settings.timeout_seconds is not None and settings.timeout_seconds <= 0:
        errors.append("LLM 超时时间必须为正数，或留空表示不限制。")
    if settings.llm_retry_max_delay < settings.llm_retry_initial_delay:
        errors.append("最大重试延迟不能小于初始重试延迟。")
    if settings.chunk_pages <= 0:
        errors.append("Chunk 页数必须为正数。")
    if settings.structure_chunk_pages <= 0:
        errors.append("结构规划 Chunk 页数必须为正数。")
    if settings.structure_max_pages <= 0:
        errors.append("结构规划最大页数必须为正数。")
    if settings.max_tokens <= 0:
        errors.append("Max tokens 必须为正数。")
    if settings.prefetch_chunks < 0:
        errors.append("预渲染 Chunk 数不能为负数。")
    if settings.llm_retries < 0:
        errors.append("LLM 重试次数不能为负数。")
    if settings.llm_max_concurrency <= 0:
        errors.append("LLM 并发数必须为正数。")
    if settings.llm_min_request_interval < 0:
        errors.append("请求间隔不能为负数。")
    if settings.batch_workers <= 0:
        errors.append("批量 Worker 必须为正数。")
    if settings.clear_cache and not settings.cache_enabled:
        errors.append("禁用缓存时不能清理缓存。")
    if settings.temperature < 0:
        errors.append("Temperature 不能为负数。")

    return errors


def _parse_pages(pages: str) -> list[int] | None:
    text = pages.strip()
    if not text:
        return []

    resolved: list[int] = []
    try:
        for chunk in text.split(","):
            item = chunk.strip()
            if not item:
                continue
            if "-" in item:
                start_text, end_text = item.split("-", 1)
                start = int(start_text.strip())
                end = int(end_text.strip())
                if start <= 0 or end <= 0 or end < start:
                    return None
                resolved.extend(range(start, end + 1))
            else:
                page = int(item)
                if page <= 0:
                    return None
                resolved.append(page)
    except ValueError:
        return None

    return resolved if resolved else None
