"""GUI-only path selection state for PDF input and output directories."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PureWindowsPath


class GuiInputKind(str, Enum):
    """PDF input kinds exposed by the GUI input selector."""

    single_file = "single_file"
    multiple_files = "multiple_files"
    directory = "directory"


INPUT_KIND_LABELS = {
    GuiInputKind.single_file: "单个 PDF",
    GuiInputKind.multiple_files: "多个 PDF",
    GuiInputKind.directory: "目录批量",
}


@dataclass(frozen=True)
class GuiInputSelection:
    """Current PDF input selection kept by the GUI layer."""

    kind: GuiInputKind
    paths: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def empty(cls, kind: GuiInputKind = GuiInputKind.single_file) -> "GuiInputSelection":
        return cls(kind=kind)

    @classmethod
    def from_single_file(cls, path: str) -> "GuiInputSelection":
        return cls(kind=GuiInputKind.single_file, paths=(path,)) if _is_pdf_path(path) else cls.empty()

    @classmethod
    def from_multiple_files(cls, paths: list[str] | tuple[str, ...]) -> "GuiInputSelection":
        pdf_paths = tuple(_deduplicate(path for path in paths if _is_pdf_path(path)))
        return cls(kind=GuiInputKind.multiple_files, paths=pdf_paths)

    @classmethod
    def from_directory(cls, path: str) -> "GuiInputSelection":
        return cls(kind=GuiInputKind.directory, paths=(path,)) if path else cls.empty(GuiInputKind.directory)

    @property
    def is_valid(self) -> bool:
        return bool(self.paths)

    def display_text(self) -> str:
        if not self.paths:
            return ""
        if self.kind == GuiInputKind.multiple_files:
            count = len(self.paths)
            if count == 1:
                return self.paths[0]
            return f"{self.paths[0]} 等 {count} 个文件"
        return self.paths[0]


@dataclass(frozen=True)
class GuiPathSelectionState:
    """Path selections required before a GUI task can be added."""

    input_selection: GuiInputSelection = field(default_factory=GuiInputSelection.empty)
    output_directory: str = ""

    @property
    def can_add_task(self) -> bool:
        return self.input_selection.is_valid and bool(self.output_directory)


def input_kind_from_label(label: str) -> GuiInputKind:
    """Resolve the Chinese combo-box label to a stable input kind."""
    for kind, kind_label in INPUT_KIND_LABELS.items():
        if label == kind_label:
            return kind
    raise ValueError(f"未知输入类型：{label}")


def _is_pdf_path(path: str) -> bool:
    return bool(path) and PureWindowsPath(path).suffix.lower() == ".pdf"


def _deduplicate(paths: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        text = str(path)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result
