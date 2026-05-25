"""Tests for local LaTeX build configuration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="latexmk is not installed")
def test_latexmk_uses_flat_out_and_per_target_build_for_single_file(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (tmp_path / "src" / "texbook").mkdir()
    (tmp_path / ".latexmkrc").write_text(
        (ROOT / ".latexmkrc").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (src_dir / "test.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nprobe\n\\end{document}\n",
        encoding="utf-8",
    )

    result = _run(
        ["latexmk", "-dir-report-only", "src/test.tex"],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    output = result.stdout + result.stderr
    assert f"'{tmp_path / 'build' / 'test'}'" in output
    assert f"'{tmp_path / 'out'}'" in output


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="latexmk is not installed")
def test_latexmk_uses_project_parent_name_for_main_entrypoint(tmp_path):
    project_dir = tmp_path / "src" / "book"
    project_dir.mkdir(parents=True)
    (tmp_path / "src" / "texbook").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".latexmkrc").write_text(
        (ROOT / ".latexmkrc").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (project_dir / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nprobe\n\\end{document}\n",
        encoding="utf-8",
    )

    result = _run(
        ["latexmk", "-dir-report-only", "src/book/main.tex"],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    output = result.stdout + result.stderr
    assert f"'{tmp_path / 'build' / 'book'}'" in output
    assert f"'{tmp_path / 'out'}'" in output


def test_post_build_moves_only_current_job_outputs(tmp_path):
    repo = tmp_path
    source_dir = repo / "src" / "book"
    source_dir.mkdir(parents=True)
    out_dir = repo / "out"
    build_dir = repo / "build" / "book"
    out_dir.mkdir(parents=True)
    build_dir.mkdir(parents=True)

    (source_dir / "book.pdf").write_text("pdf", encoding="utf-8")
    (source_dir / "book.aux").write_text("aux", encoding="utf-8")
    (source_dir / "figure.pdf").write_text("figure", encoding="utf-8")
    (out_dir / "book.synctex.gz").write_text("synctex", encoding="utf-8")
    (build_dir / "other.pdf").write_text("other", encoding="utf-8")

    result = _run(
        [
            "bash",
            str(ROOT / "scripts" / "post-build.sh"),
            str(repo),
            "book",
            str(build_dir),
            str(out_dir),
            "main.tex",
        ],
        cwd=source_dir,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert (out_dir / "book.pdf").read_text(encoding="utf-8") == "pdf"
    assert (build_dir / "book.aux").read_text(encoding="utf-8") == "aux"
    assert (build_dir / "book.synctex.gz").read_text(encoding="utf-8") == "synctex"
    assert (source_dir / "figure.pdf").read_text(encoding="utf-8") == "figure"
    assert (build_dir / "other.pdf").read_text(encoding="utf-8") == "other"
    assert not (source_dir / "book.pdf").exists()
    assert not (source_dir / "book.aux").exists()
    assert not (out_dir / "book.synctex.gz").exists()


@pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="git repository is not available",
)
def test_gitignore_treats_directory_project_tex_as_generated():
    result = _run(
        [
            "git",
            "check-ignore",
            "-v",
            "src/book/main.tex",
            "out/book.pdf",
            "build/book/book.aux",
        ],
        cwd=ROOT,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    output = result.stdout + result.stderr
    assert "src/**/*.tex" in output
    assert "out/*" in output
    assert "build/*" in output
