"""Build directory-style LaTeX project outputs."""

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Sequence

from ..complex_content import collect_complex_content_candidates, complex_content_metadata
from ..structure import StructureItemKind, StructurePlan, StructurePlanItem
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


@dataclass(frozen=True)
class LatexProjectSection:
    """Body fragments assigned to one semantic project section."""

    item: StructurePlanItem
    fragments: Sequence[str]


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
        metadata = complex_content_metadata(
            collect_complex_content_candidates(
                fragments=cleaned_fragments,
                notes=notes or [],
            )
        )

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
            metadata=metadata,
        )

    def build_from_plan(
        self,
        *,
        title: str,
        sections: Sequence[LatexProjectSection],
        structure_plan: StructurePlan,
        notes: Sequence[str] | None = None,
        show_date: bool = False,
    ) -> LatexProjectResult:
        """Build a project whose files follow a semantic structure plan."""
        section_files = self._planned_section_files(sections)
        input_entries = [
            (section.item.kind, path)
            for section, path in zip(sections, section_files, strict=True)
        ]
        cleaned_section_fragments = [
            self.latex.clean_body_fragments(section.fragments)
            for section in sections
        ]
        all_fragments = [
            fragment
            for fragments in cleaned_section_fragments
            for fragment in fragments
        ]
        metadata = {
            "structure_plan": structure_plan.to_metadata(),
            **complex_content_metadata(
                collect_complex_content_candidates(
                    fragments=all_fragments,
                    notes=notes or [],
                )
            ),
        }

        files: dict[PurePosixPath, str] = {
            PurePosixPath("preamble.tex"): self._build_preamble(),
        }
        for section, path, fragments in zip(
            sections,
            section_files,
            cleaned_section_fragments,
            strict=True,
        ):
            files[path] = self._build_section_file(section, fragments)

        entrypoint = PurePosixPath("main.tex")
        files[entrypoint] = self._build_main(
            title=title,
            chapter_paths=[path for _, path in input_entries],
            notes=notes or [],
            show_date=show_date,
            input_kinds=[kind for kind, _ in input_entries],
        )
        return LatexProjectResult(
            files=files,
            entrypoint=entrypoint,
            notes=list(notes or []),
            metadata=metadata,
        )

    def _build_main(
        self,
        *,
        title: str,
        chapter_paths: Sequence[PurePosixPath],
        notes: Sequence[str],
        show_date: bool,
        input_kinds: Sequence[StructureItemKind] | None = None,
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

        emitted_appendix = False
        resolved_input_kinds = input_kinds or [StructureItemKind.chapter] * len(chapter_paths)
        for kind, path in zip(resolved_input_kinds, chapter_paths, strict=True):
            if kind == StructureItemKind.appendix and not emitted_appendix:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(r"\appendix")
                lines.append("")
                emitted_appendix = True
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

    def _planned_section_files(
        self,
        sections: Sequence[LatexProjectSection],
    ) -> list[PurePosixPath]:
        chapter_count = sum(
            1 for section in sections if section.item.kind == StructureItemKind.chapter
        )
        appendix_count = sum(
            1 for section in sections if section.item.kind == StructureItemKind.appendix
        )
        frontmatter_count = sum(
            1 for section in sections if section.item.kind == StructureItemKind.frontmatter
        )
        chapter_width = max(2, len(str(chapter_count)))
        appendix_width = max(2, len(str(appendix_count)))
        frontmatter_width = max(2, len(str(frontmatter_count)))

        chapter_index = 0
        appendix_index = 0
        frontmatter_index = 0
        paths: list[PurePosixPath] = []
        for section in sections:
            if section.item.kind == StructureItemKind.frontmatter:
                frontmatter_index += 1
                name = (
                    "frontmatter"
                    if frontmatter_count == 1
                    else f"frontmatter{frontmatter_index:0{frontmatter_width}d}"
                )
                paths.append(PurePosixPath("chapters") / f"{name}.tex")
            elif section.item.kind == StructureItemKind.appendix:
                appendix_index += 1
                paths.append(
                    PurePosixPath("appendices")
                    / f"appendix{appendix_index:0{appendix_width}d}.tex"
                )
            else:
                chapter_index += 1
                paths.append(
                    PurePosixPath("chapters")
                    / f"chapter{chapter_index:0{chapter_width}d}.tex"
                )
        return paths

    def _build_section_file(
        self,
        section: LatexProjectSection,
        cleaned_fragments: Sequence[str],
    ) -> str:
        body = "\n\n".join(cleaned_fragments).strip()
        titled_body = self._ensure_section_title(section.item, body)
        return self._ensure_trailing_newline(titled_body)

    def _ensure_section_title(self, item: StructurePlanItem, body: str) -> str:
        if item.kind == StructureItemKind.frontmatter:
            title_command = r"\section*{" + self.latex._escape_latex(item.title) + "}"
        else:
            title_command = r"\section{" + self.latex._escape_latex(item.title) + "}"

        if self._starts_with_matching_section(body, item.title):
            return body
        if not body:
            return title_command
        return title_command + "\n\n" + body

    def _starts_with_matching_section(self, body: str, title: str) -> bool:
        match = _LEADING_SECTION_RE.match(body.strip())
        if not match:
            return False
        normalized_existing = " ".join(match.group(1).split())
        normalized_title = " ".join(title.split())
        return normalized_existing == normalized_title

    def _input_path(self, path: PurePosixPath) -> str:
        return str(path.with_suffix(""))

    def _ensure_trailing_newline(self, text: str) -> str:
        return text if text.endswith("\n") else text + "\n"


_LEADING_SECTION_RE = re.compile(r"^\\section\*?\{([^{}\n]+)\}")
