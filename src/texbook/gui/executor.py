"""Background execution helpers for GUI conversion tasks."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import shutil
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
OverwriteConfirmer = Callable[["GuiOverwriteConfirmationRequest"], bool]


@dataclass
class GuiOverwriteConfirmationRequest:
    """Blocking overwrite request sent from a worker to the GUI thread."""

    task_id: str
    task_label: str
    target: Path
    output_kind: GuiOutputKind
    summary: str
    details: str
    approved: bool = False
    _event: Event = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._event = Event()

    def resolve(self, approved: bool) -> None:
        self.approved = approved
        self._event.set()

    def wait(self) -> bool:
        self._event.wait()
        return self.approved


@dataclass(frozen=True)
class GuiWritePolicy:
    """GUI write behavior for one conversion task."""

    confirm_overwrite: bool = True
    overwrite_confirmer: OverwriteConfirmer | None = None
    task_id: str = ""
    task_label: str = ""


def run_gui_conversion_task(
    task: GuiConversionTask,
    *,
    cancellation_token: GuiCancellationToken | None = None,
    progress_reporter: Callable[[ProgressEvent], None] | None = None,
    converter_factory: ConverterFactory | None = None,
    overwrite_confirmer: OverwriteConfirmer | None = None,
) -> GuiTaskExecutionResult:
    """Run one GUI conversion task and write its result using GUI overwrite policy."""
    token = cancellation_token or GuiCancellationToken()
    write_policy = GuiWritePolicy(
        confirm_overwrite=task.confirm_overwrite,
        overwrite_confirmer=overwrite_confirmer,
        task_id=task.task_id,
        task_label=task.label,
    )

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
        entrypoint = write_project_result(
            project,
            task.output_target.path,
            policy=write_policy,
        )
        return GuiTaskExecutionResult(
            task_id=task.task_id,
            result=str(entrypoint),
            notes=tuple(project.notes),
        )

    result = converter.convert(task.source_pdf, pages=task.core.pages)
    token.raise_if_canceled()
    output = write_tex_result(result.latex, task.output_target.path, policy=write_policy)
    return GuiTaskExecutionResult(
        task_id=task.task_id,
        result=str(output),
        notes=tuple(result.notes),
    )


def write_tex_result(
    latex: str,
    target: Path,
    *,
    policy: GuiWritePolicy | None = None,
) -> Path:
    """Write or overwrite a `.tex` output according to the GUI write policy."""
    target = target.expanduser()
    if target.exists() and target.is_dir():
        raise GuiTaskExecutionError(f"输出文件路径已存在但不是文件：{target}")
    if target.exists():
        _confirm_overwrite(
            target=target,
            output_kind=GuiOutputKind.tex_file,
            summary="覆盖已有 LaTeX 文件",
            details="将替换目标 .tex 文件，同目录其它文件不会被清理。",
            policy=policy,
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(latex, encoding="utf-8")
    return target


def write_project_result(
    project: LatexProjectResult,
    target_dir: Path,
    *,
    policy: GuiWritePolicy | None = None,
) -> Path:
    """Write or overwrite a project output according to the GUI write policy."""
    target_dir = target_dir.expanduser()
    if target_dir.exists() and not target_dir.is_dir():
        raise GuiTaskExecutionError(f"项目输出路径已存在但不是目录：{target_dir}")
    if target_dir.exists() and any(target_dir.iterdir()):
        _ensure_safe_project_cleanup_target(target_dir)
        _confirm_overwrite(
            target=target_dir,
            output_kind=GuiOutputKind.project,
            summary="清理并覆盖目录化项目",
            details="将清空该项目目录中的旧内容，然后写入新的项目文件。",
            policy=policy,
        )
        _clear_directory(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for relative_path, content in project.files.items():
        destination = _project_file_destination(target_dir, relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    return _project_file_destination(target_dir, project.entrypoint)


def write_tex_result_conservatively(latex: str, target: Path) -> Path:
    """Backward-compatible safe write helper from the task 8 stage."""
    return write_tex_result(
        latex,
        target,
        policy=GuiWritePolicy(confirm_overwrite=True),
    )


def write_project_result_conservatively(project: LatexProjectResult, target_dir: Path) -> Path:
    """Backward-compatible safe project write helper from the task 8 stage."""
    return write_project_result(
        project,
        target_dir,
        policy=GuiWritePolicy(confirm_overwrite=True),
    )


class GuiTaskExecutor(QObject):
    """Execute GUI conversion tasks on a bounded background thread pool."""

    task_started = Signal(str)
    task_progress = Signal(str, object)
    task_completed = Signal(str, str, object)
    task_failed = Signal(str, str)
    task_canceling = Signal(str)
    task_canceled = Signal(str)
    overwrite_confirmation_requested = Signal(object)
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
                overwrite_confirmer=self._confirm_overwrite,
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

    def _confirm_overwrite(self, request: GuiOverwriteConfirmationRequest) -> bool:
        if self.receivers("2overwrite_confirmation_requested(PyObject)") <= 0:
            raise GuiTaskExecutionError(f"需要确认覆盖：{request.target}")
        self.overwrite_confirmation_requested.emit(request)
        return request.wait()


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


def _confirm_overwrite(
    *,
    target: Path,
    output_kind: GuiOutputKind,
    summary: str,
    details: str,
    policy: GuiWritePolicy | None,
) -> None:
    policy = policy or GuiWritePolicy()
    if not policy.confirm_overwrite:
        return
    if policy.overwrite_confirmer is None:
        raise GuiTaskExecutionError(f"需要确认覆盖：{target}")

    request = GuiOverwriteConfirmationRequest(
        task_id=policy.task_id,
        task_label=policy.task_label,
        target=target,
        output_kind=output_kind,
        summary=summary,
        details=details,
    )
    if not policy.overwrite_confirmer(request):
        raise GuiTaskExecutionError(f"用户取消覆盖：{target}")


def _ensure_safe_project_cleanup_target(target_dir: Path) -> None:
    resolved = target_dir.resolve(strict=False)
    repository_root = Path(__file__).resolve().parents[3]
    package_dir = (repository_root / "src" / "texbook").resolve(strict=False)
    dangerous_targets = {
        Path(resolved.anchor).resolve(strict=False),
        Path.home().resolve(strict=False),
        repository_root.resolve(strict=False),
        (repository_root / "src").resolve(strict=False),
        package_dir,
    }
    if resolved in dangerous_targets or package_dir in resolved.parents:
        raise GuiTaskExecutionError(f"拒绝清理危险项目目录：{target_dir}")
    if (target_dir / ".git").exists() or (target_dir / "pyproject.toml").exists():
        raise GuiTaskExecutionError(f"拒绝清理疑似项目根目录：{target_dir}")


def _clear_directory(target_dir: Path) -> None:
    for child in target_dir.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _format_task_error(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__
