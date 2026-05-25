"""Background execution helpers for GUI conversion tasks."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from threading import Event, Lock
from typing import Protocol

from PySide6.QtCore import QObject, Signal

from texbook.convert import LatexProjectResult
from texbook.gui.settings import GuiOutputKind
from texbook.gui.tasks import GuiConversionTask
from texbook.llm.factory import build_pdf_converter
from texbook.llm.scheduler import ProgressEvent


class GuiTaskCanceled(Exception):
    """Raised inside a GUI worker when cancellation is requested."""


class GuiTaskExecutionError(RuntimeError):
    """Raised when one GUI task cannot be converted or written."""


class GuiCancellationToken:
    """Thread-safe cooperative cancellation token for GUI tasks."""

    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_cancellation_requested(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_canceled(self) -> None:
        if self.is_cancellation_requested:
            raise GuiTaskCanceled("任务已取消")


@dataclass(frozen=True)
class GuiTaskExecutionResult:
    """Result emitted after one background task finishes."""

    task_id: str
    result: str = ""
    notes: tuple[str, ...] = ()


class GuiTaskConverter(Protocol):
    """Subset of the core converter used by the GUI executor."""

    def convert(self, pdf_path: Path, *, pages: list[int] | None = None): ...

    def convert_project(self, pdf_path: Path, *, pages: list[int] | None = None) -> LatexProjectResult: ...


ConverterFactory = Callable[[GuiConversionTask, Callable[[ProgressEvent], None]], GuiTaskConverter]


def run_gui_conversion_task(
    task: GuiConversionTask,
    *,
    cancellation_token: GuiCancellationToken | None = None,
    progress_reporter: Callable[[ProgressEvent], None] | None = None,
    converter_factory: ConverterFactory | None = None,
) -> GuiTaskExecutionResult:
    """Run one GUI conversion task and write its result conservatively."""
    token = cancellation_token or GuiCancellationToken()

    def reporter(event: ProgressEvent) -> None:
        token.raise_if_canceled()
        if progress_reporter is not None:
            progress_reporter(event)
        token.raise_if_canceled()

    token.raise_if_canceled()
    converter = _build_task_converter(task, reporter, converter_factory=converter_factory)
    token.raise_if_canceled()

    if task.output_target.kind == GuiOutputKind.project:
        project = converter.convert_project(task.source_pdf, pages=task.core.pages)
        token.raise_if_canceled()
        entrypoint = write_project_result_conservatively(project, task.output_target.path)
        return GuiTaskExecutionResult(
            task_id=task.task_id,
            result=str(entrypoint),
            notes=tuple(project.notes),
        )

    result = converter.convert(task.source_pdf, pages=task.core.pages)
    token.raise_if_canceled()
    output = write_tex_result_conservatively(result.latex, task.output_target.path)
    return GuiTaskExecutionResult(
        task_id=task.task_id,
        result=str(output),
        notes=tuple(result.notes),
    )


def write_tex_result_conservatively(latex: str, target: Path) -> Path:
    """Write a `.tex` output only when the target file does not exist."""
    target = target.expanduser()
    if target.exists():
        raise GuiTaskExecutionError(
            f"输出文件已存在：{target}。覆盖确认与清理将在后续任务接入。"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(latex, encoding="utf-8")
    return target


def write_project_result_conservatively(project: LatexProjectResult, target_dir: Path) -> Path:
    """Write a project output only into a missing or empty directory."""
    target_dir = target_dir.expanduser()
    if target_dir.exists() and not target_dir.is_dir():
        raise GuiTaskExecutionError(f"项目输出路径已存在但不是目录：{target_dir}")
    if target_dir.exists() and any(target_dir.iterdir()):
        raise GuiTaskExecutionError(
            f"项目输出目录非空：{target_dir}。覆盖确认与清理将在后续任务接入。"
        )
    target_dir.mkdir(parents=True, exist_ok=True)

    for relative_path, content in project.files.items():
        destination = _project_file_destination(target_dir, relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    return _project_file_destination(target_dir, project.entrypoint)


class GuiTaskExecutor(QObject):
    """Execute GUI conversion tasks on a bounded background thread pool."""

    task_started = Signal(str)
    task_progress = Signal(str, object)
    task_completed = Signal(str, str, object)
    task_failed = Signal(str, str)
    task_canceling = Signal(str)
    task_canceled = Signal(str)
    all_finished = Signal()

    def __init__(
        self,
        tasks: list[GuiConversionTask],
        *,
        max_workers: int = 1,
        converter_factory: ConverterFactory | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tasks = list(tasks)
        self._max_workers = max(1, int(max_workers))
        self._converter_factory = converter_factory
        self._tokens = {task.task_id: GuiCancellationToken() for task in self._tasks}
        self._executor: ThreadPoolExecutor | None = None
        self._remaining = len(self._tasks)
        self._lock = Lock()
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started and self._remaining > 0

    def start(self) -> None:
        """Start all queued tasks."""
        if self._started:
            return
        self._started = True
        if not self._tasks:
            self.all_finished.emit()
            return

        self._executor = ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="texbook-gui")
        for task in self._tasks:
            future = self._executor.submit(self._run_task, task)
            future.add_done_callback(lambda _future, task_id=task.task_id: self._mark_finished(task_id))

    def cancel_task(self, task_id: str) -> None:
        """Request cooperative cancellation for one task."""
        token = self._tokens.get(task_id)
        if token is None:
            return
        token.cancel()
        self.task_canceling.emit(task_id)

    def cancel_all(self) -> None:
        """Request cooperative cancellation for all unfinished tasks."""
        for task_id in list(self._tokens):
            self.cancel_task(task_id)

    def shutdown(self) -> None:
        """Stop accepting new work and request cancellation."""
        self.cancel_all()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    def _run_task(self, task: GuiConversionTask) -> None:
        token = self._tokens[task.task_id]
        try:
            token.raise_if_canceled()
            self.task_started.emit(task.task_id)
            result = run_gui_conversion_task(
                task,
                cancellation_token=token,
                progress_reporter=lambda event: self.task_progress.emit(task.task_id, event),
                converter_factory=self._converter_factory,
            )
        except GuiTaskCanceled:
            self.task_canceled.emit(task.task_id)
            return
        except Exception as exc:
            self.task_failed.emit(task.task_id, _format_task_error(exc))
            return

        self.task_completed.emit(result.task_id, result.result, result.notes)

    def _mark_finished(self, task_id: str) -> None:
        with self._lock:
            self._remaining -= 1
            finished = self._remaining <= 0
        self._tokens.pop(task_id, None)
        if finished:
            if self._executor is not None:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None
            self.all_finished.emit()


def _build_task_converter(
    task: GuiConversionTask,
    progress_reporter: Callable[[ProgressEvent], None],
    *,
    converter_factory: ConverterFactory | None,
) -> GuiTaskConverter:
    if converter_factory is not None:
        return converter_factory(task, progress_reporter)
    return build_pdf_converter(
        task.core.llm_config,
        options=task.core.conversion_options,
        progress_reporter=progress_reporter,
    )


def _project_file_destination(target_dir: Path, relative_path: PurePosixPath) -> Path:
    return target_dir.joinpath(*relative_path.parts)


def _format_task_error(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__
