"""GUI conversion task specifications and creation helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PureWindowsPath
from uuid import uuid4

from texbook.gui.core_adapter import GuiCoreConversionBundle, build_core_conversion_bundle
from texbook.gui.display import GuiLanguage
from texbook.gui.i18n import tr
from texbook.gui.selection import GuiInputKind
from texbook.gui.settings import GuiConversionSettings, GuiOutputKind
from texbook.llm.scheduler import ProgressEvent


class GuiTaskStatus(str, Enum):
    """Lifecycle states for GUI-created conversion tasks."""

    pending = "pending"
    running = "running"
    canceling = "canceling"
    canceled = "canceled"
    completed = "completed"
    failed = "failed"


class GuiTaskStage(str, Enum):
    """User-visible conversion stages tracked by the GUI task list."""

    waiting = "waiting"
    extracting = "extracting"
    document_class = "document_class"
    structure = "structure"
    chunk = "chunk"
    title = "title"
    finalizing = "finalizing"
    canceled = "canceled"
    completed = "completed"
    failed = "failed"


TASK_STAGE_LABEL_KEYS = {
    GuiTaskStage.waiting: "task.stage.waiting",
    GuiTaskStage.extracting: "task.stage.extracting",
    GuiTaskStage.document_class: "task.stage.document_class",
    GuiTaskStage.structure: "task.stage.structure",
    GuiTaskStage.chunk: "task.stage.chunk",
    GuiTaskStage.title: "task.stage.title",
    GuiTaskStage.finalizing: "task.stage.finalizing",
    GuiTaskStage.canceled: "task.stage.canceled",
    GuiTaskStage.completed: "task.stage.completed",
    GuiTaskStage.failed: "task.stage.failed",
}

TASK_STATUS_LABEL_KEYS = {
    GuiTaskStatus.pending: "task.status.pending",
    GuiTaskStatus.running: "task.status.running",
    GuiTaskStatus.canceling: "task.status.canceling",
    GuiTaskStatus.canceled: "task.status.canceled",
    GuiTaskStatus.completed: "task.status.completed",
    GuiTaskStatus.failed: "task.status.failed",
}

TASK_STAGE_LABELS = {
    stage: tr(GuiLanguage.zh_CN, key) for stage, key in TASK_STAGE_LABEL_KEYS.items()
}

TASK_STATUS_LABELS = {
    status: tr(GuiLanguage.zh_CN, key) for status, key in TASK_STATUS_LABEL_KEYS.items()
}

TERMINAL_TASK_STATUSES = {
    GuiTaskStatus.canceled,
    GuiTaskStatus.completed,
    GuiTaskStatus.failed,
}


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


@dataclass(frozen=True)
class GuiTaskRuntimeUpdate:
    """Partial task state update produced by a future worker or tests."""

    status: GuiTaskStatus | None = None
    stage: GuiTaskStage | None = None
    progress: int | None = None
    cache_hits: int | None = None
    retries: int | None = None
    error: str | None = None
    result: str | None = None
    notes: tuple[str, ...] | None = None
    recent_event: str | None = None
    recent_event_key: str | None = None
    recent_event_args: dict[str, object] | None = None


@dataclass
class GuiTaskViewState:
    """Mutable display state for one GUI conversion task."""

    task: GuiConversionTask
    status: GuiTaskStatus = GuiTaskStatus.pending
    stage: GuiTaskStage = GuiTaskStage.waiting
    progress: int = 0
    cache_hits: int = 0
    retries: int = 0
    error: str = ""
    result: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)
    recent_event: str = ""
    recent_event_key: str = ""
    recent_event_args: dict[str, object] = field(default_factory=dict)

    @property
    def task_id(self) -> str:
        return self.task.task_id

    @property
    def label(self) -> str:
        return self.task.label or _path_name(self.task.source_pdf)

    @property
    def status_label(self) -> str:
        return task_status_label(self.status)

    @property
    def stage_label(self) -> str:
        return task_stage_label(self.stage)


def task_status_label(
    status: GuiTaskStatus,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> str:
    """Return a localized task status label."""
    return tr(language, TASK_STATUS_LABEL_KEYS[status])


def task_stage_label(
    stage: GuiTaskStage,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> str:
    """Return a localized task stage label."""
    return tr(language, TASK_STAGE_LABEL_KEYS[stage])


def task_recent_event_text(
    state: GuiTaskViewState,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> str:
    """Return the latest task event in the requested language when possible."""
    if state.recent_event_key:
        return tr(language, state.recent_event_key, **state.recent_event_args)
    return state.recent_event


def create_task_view_state(task: GuiConversionTask) -> GuiTaskViewState:
    """Create the initial visual state for a newly added GUI task."""
    return GuiTaskViewState(task=task, notes=task.notes)


def apply_task_update(
    state: GuiTaskViewState,
    update: GuiTaskRuntimeUpdate,
) -> GuiTaskViewState:
    """Apply a partial display update to one task state."""
    if update.status is not None:
        state.status = update.status
    if update.stage is not None:
        state.stage = update.stage
    if update.progress is not None:
        state.progress = _clamp_progress(update.progress)
    if update.cache_hits is not None:
        state.cache_hits = max(0, update.cache_hits)
    if update.retries is not None:
        state.retries = max(0, update.retries)
    if update.error is not None:
        state.error = update.error
    if update.result is not None:
        state.result = update.result
    if update.notes is not None:
        state.notes = update.notes
    if update.recent_event is not None:
        state.recent_event = update.recent_event
        state.recent_event_key = update.recent_event_key or ""
        state.recent_event_args = update.recent_event_args or {}
    return state


def mark_task_running(
    state: GuiTaskViewState,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> GuiTaskViewState:
    """Mark a task as running without starting conversion in this layer."""
    if state.status in TERMINAL_TASK_STATUSES:
        return state
    state.status = GuiTaskStatus.running
    state.progress = max(state.progress, 5)
    _set_recent_event(state, "task.event.started", language)
    return state


def mark_task_canceling(
    state: GuiTaskViewState,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> GuiTaskViewState:
    """Mark a task as canceling while a worker is winding down."""
    if state.status in TERMINAL_TASK_STATUSES:
        return state
    state.status = GuiTaskStatus.canceling
    _set_recent_event(state, "task.event.canceling", language)
    return state


def mark_task_canceled(
    state: GuiTaskViewState,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> GuiTaskViewState:
    """Mark a task as canceled for visual display."""
    state.status = GuiTaskStatus.canceled
    state.stage = GuiTaskStage.canceled
    state.error = ""
    state.result = ""
    _set_recent_event(state, "task.event.canceled", language)
    return state


def mark_task_completed(
    state: GuiTaskViewState,
    *,
    result: str = "",
    notes: Iterable[str] = (),
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> GuiTaskViewState:
    """Mark a task as completed for visual display."""
    if state.status == GuiTaskStatus.canceled:
        return state
    state.status = GuiTaskStatus.completed
    state.stage = GuiTaskStage.completed
    state.progress = 100
    state.error = ""
    state.result = result or _format_output_target(state.task.output_target)
    state.notes = tuple(notes)
    _set_recent_event(state, "task.event.completed", language)
    return state


def mark_task_failed(
    state: GuiTaskViewState,
    error: str,
) -> GuiTaskViewState:
    """Mark a task as failed for visual display."""
    if state.status == GuiTaskStatus.canceled:
        return state
    state.status = GuiTaskStatus.failed
    state.stage = GuiTaskStage.failed
    state.error = error
    state.progress = min(state.progress, 99)
    state.recent_event = error
    state.recent_event_key = ""
    state.recent_event_args = {}
    return state


def apply_progress_event(
    state: GuiTaskViewState,
    event: ProgressEvent,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> GuiTaskViewState:
    """Merge one core progress event into a GUI task display state."""
    if state.status in TERMINAL_TASK_STATUSES:
        return state
    _set_recent_progress_event(state, event, language)
    if event.kind == "stage_started":
        _mark_task_active(state)
        state.stage = _stage_for_operation(event.operation)
        state.progress = max(state.progress, _stage_start_progress(event.operation))
        return state
    if event.kind == "stage_completed":
        _mark_task_active(state)
        state.stage = _stage_for_operation(event.operation)
        state.progress = max(state.progress, _stage_completed_progress(event.operation, event))
        return state
    if event.kind == "cache_hit":
        _mark_task_active(state)
        state.cache_hits += 1
        state.progress = max(state.progress, _stage_start_progress(event.operation))
        return state
    if event.kind == "retry_scheduled":
        _mark_task_active(state)
        state.retries += 1
        return state
    if event.kind == "request_started":
        _mark_task_active(state)
        state.progress = max(state.progress, _stage_start_progress(event.operation))
        return state
    if event.kind == "request_failed":
        return mark_task_failed(state, event.error or tr(language, "task.event.request_failed"))
    if event.kind == "request_completed":
        _mark_task_active(state)
        state.progress = max(state.progress, _stage_completed_progress(event.operation, event))
        return state
    return state


def create_conversion_tasks(
    settings: GuiConversionSettings,
    *,
    repo_root: Path | None = None,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> list[GuiConversionTask]:
    """Create pending in-memory tasks from the current GUI settings."""
    if not settings.path_state.can_add_task:
        raise GuiTaskCreationError(tr(language, "error.select_input_output"))
    pdf_paths = _resolve_input_pdfs(settings, language=language)
    if not pdf_paths:
        raise GuiTaskCreationError(tr(language, "error.no_matching_pdf"))

    targets = _resolve_output_targets(settings, pdf_paths)
    _validate_no_target_collisions(pdf_paths, targets, language=language)
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


def _resolve_input_pdfs(
    settings: GuiConversionSettings,
    *,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> list[Path]:
    selection = settings.path_state.input_selection
    if selection.kind == GuiInputKind.directory:
        if not selection.paths:
            return []
        directory = Path(selection.paths[0]).expanduser()
        if not directory.is_dir():
            raise GuiTaskCreationError(
                tr(language, "error.pdf_directory_missing", directory=directory)
            )
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
    *,
    language: GuiLanguage | str = GuiLanguage.zh_CN,
) -> None:
    seen: dict[Path, Path] = {}
    for pdf_path, target in zip(pdf_paths, targets, strict=True):
        resolved = target.path.resolve(strict=False)
        existing = seen.get(resolved)
        if existing is not None:
            raise GuiTaskCreationError(
                tr(
                    language,
                    "error.target_collision",
                    existing=existing.name,
                    current=pdf_path.name,
                    target=target.path,
                )
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
        api_key_source=settings.api_key_source,
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


def _format_output_target(target: GuiOutputTarget) -> str:
    suffix = "项目" if target.kind == GuiOutputKind.project else "LaTeX"
    return f"{suffix}：{target.path}"


def _clamp_progress(value: int) -> int:
    return max(0, min(100, int(value)))


def _mark_task_active(state: GuiTaskViewState) -> None:
    if state.status != GuiTaskStatus.canceling:
        state.status = GuiTaskStatus.running


def _set_recent_event(
    state: GuiTaskViewState,
    key: str,
    language: GuiLanguage | str,
    **kwargs: object,
) -> None:
    state.recent_event_key = key
    state.recent_event_args = dict(kwargs)
    state.recent_event = tr(language, key, **kwargs)


def _set_recent_progress_event(
    state: GuiTaskViewState,
    event: ProgressEvent,
    language: GuiLanguage | str,
) -> None:
    key, kwargs = _event_summary_template(event)
    _set_recent_event(state, key, language, **kwargs)


def _stage_for_operation(operation: str) -> GuiTaskStage:
    if operation == "extract":
        return GuiTaskStage.extracting
    if operation == "document_class":
        return GuiTaskStage.document_class
    if operation == "structure":
        return GuiTaskStage.structure
    if operation == "chunk":
        return GuiTaskStage.chunk
    if operation == "title":
        return GuiTaskStage.title
    if operation == "conversion":
        return GuiTaskStage.finalizing
    return GuiTaskStage.finalizing


def _stage_start_progress(operation: str) -> int:
    return {
        "conversion": 5,
        "extract": 12,
        "document_class": 22,
        "structure": 35,
        "chunk": 45,
        "title": 90,
    }.get(operation, 10)


def _stage_completed_progress(operation: str, event: ProgressEvent) -> int:
    if operation == "conversion":
        return 95
    if operation == "extract":
        return 20
    if operation == "document_class":
        return 32
    if operation == "structure":
        return 42
    if operation == "title":
        return 95
    if operation == "chunk":
        chunk_index = _metadata_int(event, "chunk_index")
        total_chunks = _metadata_int(event, "total_chunks")
        if chunk_index is not None and total_chunks:
            return _clamp_progress(45 + round(40 * chunk_index / total_chunks))
        return 75
    return _stage_start_progress(operation)


def _metadata_int(event: ProgressEvent, key: str) -> int | None:
    value = event.metadata.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_summary(event: ProgressEvent) -> str:
    key, kwargs = _event_summary_template(event)
    return tr(GuiLanguage.zh_CN, key, **kwargs)


def _event_summary_template(event: ProgressEvent) -> tuple[str, dict[str, object]]:
    label = event.label or event.operation
    if event.kind == "stage_started":
        return "event.stage_started", {"label": label}
    if event.kind == "stage_completed":
        return "event.stage_completed", {"label": label}
    if event.kind == "cache_hit":
        return "event.cache_hit", {"label": label}
    if event.kind == "retry_scheduled":
        delay = event.delay or 0.0
        return "event.retry_scheduled", {"label": label, "delay": f"{delay:.1f}"}
    if event.kind == "request_started":
        return "event.request_started", {"label": label}
    if event.kind == "request_completed":
        return "event.request_completed", {"label": label}
    if event.kind == "request_failed":
        return "event.request_failed", {"label": label}
    return "{label}", {"label": label}
