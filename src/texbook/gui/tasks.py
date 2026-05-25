"""GUI conversion task specifications and creation helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PureWindowsPath
from uuid import uuid4

from texbook.gui.core_adapter import GuiCoreConversionBundle, build_core_conversion_bundle
from texbook.gui.selection import GuiInputKind
from texbook.gui.settings import GuiConversionSettings, GuiOutputKind


class GuiTaskStatus(str, Enum):
    """Lifecycle states for GUI-created conversion tasks."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class GuiTaskCreationError(ValueError):
    """Raised when GUI input cannot be expanded into conversion tasks."""


@dataclass(frozen=True)
class GuiOutputTarget:
    """Resolved output target for one GUI conversion task."""

    kind: GuiOutputKind
    path: Path


@dataclass(frozen=True)
class GuiConversionTask:
    """One pending conversion task created from GUI settings."""

    task_id: str
    source_pdf: Path
    output_target: GuiOutputTarget
    core: GuiCoreConversionBundle
    confirm_overwrite: bool
    status: GuiTaskStatus = GuiTaskStatus.pending
    label: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)


def create_conversion_tasks(
    settings: GuiConversionSettings,
    *,
    repo_root: Path | None = None,
) -> list[GuiConversionTask]:
    """Create pending in-memory tasks from the current GUI settings."""
    if not settings.path_state.can_add_task:
        raise GuiTaskCreationError("请选择 PDF 输入和输出目标。")
    pdf_paths = _resolve_input_pdfs(settings)
    if not pdf_paths:
        raise GuiTaskCreationError("未找到匹配的 PDF 文件。")

    targets = _resolve_output_targets(settings, pdf_paths)
    _validate_no_target_collisions(pdf_paths, targets)
    tasks: list[GuiConversionTask] = []
    for pdf_path, target in zip(pdf_paths, targets, strict=True):
        task_settings = _settings_for_pdf(settings, pdf_path)
        core = build_core_conversion_bundle(task_settings, repo_root=repo_root)
        tasks.append(
            GuiConversionTask(
                task_id=uuid4().hex,
                source_pdf=pdf_path,
                output_target=target,
                core=core,
                confirm_overwrite=settings.confirm_overwrite,
                label=_path_name(pdf_path),
            )
        )
    return tasks


def _resolve_input_pdfs(settings: GuiConversionSettings) -> list[Path]:
    selection = settings.path_state.input_selection
    if selection.kind == GuiInputKind.directory:
        if not selection.paths:
            return []
        directory = Path(selection.paths[0]).expanduser()
        if not directory.is_dir():
            raise GuiTaskCreationError(f"PDF 目录不存在：{directory}")
        pattern = settings.batch_pattern.strip()
        return [
            path
            for path in sorted(directory.glob(pattern))
            if path.is_file() and path.suffix.lower() == ".pdf"
        ]

    return [Path(path).expanduser() for path in selection.paths if Path(path).suffix.lower() == ".pdf"]


def _resolve_output_targets(
    settings: GuiConversionSettings,
    pdf_paths: list[Path],
) -> list[GuiOutputTarget]:
    output_path = Path(settings.path_state.output_directory).expanduser()
    single_input = (
        settings.path_state.input_selection.kind == GuiInputKind.single_file
        and len(pdf_paths) == 1
    )
    if single_input:
        if settings.output_kind == GuiOutputKind.project:
            return [GuiOutputTarget(kind=GuiOutputKind.project, path=output_path)]
        return [GuiOutputTarget(kind=GuiOutputKind.tex_file, path=_with_tex_suffix(output_path))]

    targets: list[GuiOutputTarget] = []
    for pdf_path in pdf_paths:
        if settings.output_kind == GuiOutputKind.project:
            targets.append(
                GuiOutputTarget(kind=GuiOutputKind.project, path=output_path / _path_stem(pdf_path))
            )
        else:
            targets.append(
                GuiOutputTarget(kind=GuiOutputKind.tex_file, path=output_path / f"{_path_stem(pdf_path)}.tex")
            )
    return targets


def _validate_no_target_collisions(
    pdf_paths: Iterable[Path],
    targets: Iterable[GuiOutputTarget],
) -> None:
    seen: dict[Path, Path] = {}
    for pdf_path, target in zip(pdf_paths, targets, strict=True):
        resolved = target.path.resolve(strict=False)
        existing = seen.get(resolved)
        if existing is not None:
            raise GuiTaskCreationError(
                f"输出目标冲突：{existing.name} 和 {pdf_path.name} 都会写入 {target.path}"
            )
        seen[resolved] = pdf_path


def _settings_for_pdf(
    settings: GuiConversionSettings,
    pdf_path: Path,
) -> GuiConversionSettings:
    if settings.path_state.input_selection.kind == GuiInputKind.single_file:
        return settings
    return GuiConversionSettings(
        path_state=settings.path_state,
        output_kind=settings.output_kind,
        confirm_overwrite=settings.confirm_overwrite,
        batch_pattern=settings.batch_pattern,
        pages=settings.pages,
        document_class=settings.document_class,
        structure_mode=settings.structure_mode,
        structure_chunk_pages=settings.structure_chunk_pages,
        structure_max_pages=settings.structure_max_pages,
        manual_title="",
        title_source=settings.title_source,
        show_date=settings.show_date,
        beamer_title_page=settings.beamer_title_page,
        model=settings.model,
        base_url=settings.base_url,
        api_key=settings.api_key,
        prompt_preset=settings.prompt_preset,
        extra_prompt=settings.extra_prompt,
        temperature=settings.temperature,
        timeout_seconds=settings.timeout_seconds,
        max_tokens=settings.max_tokens,
        cache_enabled=settings.cache_enabled,
        cache_directory=settings.cache_directory,
        clear_cache=settings.clear_cache,
        chunk_pages=settings.chunk_pages,
        prefetch_chunks=settings.prefetch_chunks,
        llm_max_concurrency=settings.llm_max_concurrency,
        llm_min_request_interval=settings.llm_min_request_interval,
        batch_workers=settings.batch_workers,
        image_dpi=settings.image_dpi,
        image_dpi_min=settings.image_dpi_min,
        image_dpi_max=settings.image_dpi_max,
        image_format=settings.image_format,
        jpeg_quality=settings.jpeg_quality,
        llm_retries=settings.llm_retries,
        llm_retry_initial_delay=settings.llm_retry_initial_delay,
        llm_retry_max_delay=settings.llm_retry_max_delay,
        beamer_box_style=settings.beamer_box_style,
        ctex_font_profile=settings.ctex_font_profile,
    )


def _with_tex_suffix(path: Path) -> Path:
    if path.suffix.lower() == ".tex":
        return path
    return path.with_suffix(".tex")


def _path_stem(path: Path) -> str:
    return PureWindowsPath(str(path)).stem


def _path_name(path: Path) -> str:
    return PureWindowsPath(str(path)).name
