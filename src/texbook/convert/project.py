"""Build directory-style LaTeX project outputs."""

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Sequence

from .latex_converter import LatexConverter


@dataclass
class LatexProjectResult:
    """In-memory output for a directory-style LaTeX project."""

    files: dict[PurePosixPath, str]
    entrypoint: PurePosixPath
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.entrypoint not in self.files:
            raise ValueError("project entrypoint must exist in files.")
        for path in self.files:
            if path.is_absolute() or ".." in path.parts or str(path) == ".":
                raise ValueError("project file paths must be relative POSIX paths.")


class LatexProjectBuilder:
    """Build a basic multi-file LaTeX project from body fragments."""

    def __init__(self, use_ctex: bool = True):
        self.latex = LatexConverter(use_ctex=use_ctex)

    def build(
        self,
        *,
        title: str,
        fragments: Sequence[str],
        notes: Sequence[str] | None = None,
        show_date: bool = False,
    ) -> LatexProjectResult:
        """Build a project with main.tex, preamble.tex, and chunk-based chapters."""
        cleaned_fragments = self.latex.clean_body_fragments(fragments)
        chapter_paths = self._chapter_paths(len(cleaned_fragments))

        files: dict[PurePosixPath, str] = {
            PurePosixPath("preamble.tex"): self._build_preamble(),
        }
        for path, fragment in zip(chapter_paths, cleaned_fragments):
            files[path] = self._ensure_trailing_newline(fragment)

        entrypoint = PurePosixPath("main.tex")
        files[entrypoint] = self._build_main(
            title=title,
            chapter_paths=chapter_paths,
            notes=notes or [],
            show_date=show_date,
        )
        return LatexProjectResult(
            files=files,
            entrypoint=entrypoint,
            notes=list(notes or []),
            metadata={},
        )

    def _build_main(
        self,
        *,
        title: str,
        chapter_paths: Sequence[PurePosixPath],
        notes: Sequence[str],
        show_date: bool,
    ) -> str:
        lines = [
            "% !TEX program = xelatex",
            self.latex.documentclass_line(),
            r"\input{preamble}",
            "",
            *self.latex.title_block_lines(title, show_date=show_date),
            "",
            r"\begin{document}",
            r"\maketitle",
            "",
        ]
        note_lines = self.latex.note_comment_lines(notes)
        if note_lines:
            lines.extend(note_lines)
            lines.append("")

        for path in chapter_paths:
            lines.append(r"\input{" + self._input_path(path) + "}")
        if chapter_paths:
            lines.append("")
        lines.append(r"\end{document}")
        lines.append("")
        return "\n".join(lines)

    def _build_preamble(self) -> str:
        return "\n".join([*self.latex.preamble_lines(), ""])

    def _chapter_paths(self, count: int) -> list[PurePosixPath]:
        if count == 0:
            return []
        width = max(2, len(str(count)))
        return [
            PurePosixPath("chapters") / f"chapter{index:0{width}d}.tex"
            for index in range(1, count + 1)
        ]

    def _input_path(self, path: PurePosixPath) -> str:
        return str(path.with_suffix(""))

    def _ensure_trailing_newline(self, text: str) -> str:
        return text if text.endswith("\n") else text + "\n"
