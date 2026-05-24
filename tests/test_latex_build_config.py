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
def test_latexmk_mirrors_src_relative_parent_for_project_entrypoint(tmp_path):
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
    assert f"'{tmp_path / 'out' / 'book'}'" in output


def test_post_build_moves_only_current_job_outputs(tmp_path):
    repo = tmp_path
    source_dir = repo / "src" / "book"
    source_dir.mkdir(parents=True)
    out_dir = repo / "out" / "book"
    build_dir = repo / "build" / "book"
    out_dir.mkdir(parents=True)
    build_dir.mkdir(parents=True)

    (source_dir / "main.pdf").write_text("pdf", encoding="utf-8")
    (source_dir / "main.aux").write_text("aux", encoding="utf-8")
    (source_dir / "figure.pdf").write_text("figure", encoding="utf-8")
    (out_dir / "main.synctex.gz").write_text("synctex", encoding="utf-8")
    (build_dir / "other.pdf").write_text("other", encoding="utf-8")

    result = _run(
        [
            "bash",
            str(ROOT / "scripts" / "post-build.sh"),
            str(repo),
            "main",
            str(build_dir),
            str(out_dir),
            "main.tex",
        ],
        cwd=source_dir,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert (out_dir / "main.pdf").read_text(encoding="utf-8") == "pdf"
    assert (build_dir / "main.aux").read_text(encoding="utf-8") == "aux"
    assert (build_dir / "main.synctex.gz").read_text(encoding="utf-8") == "synctex"
    assert (source_dir / "figure.pdf").read_text(encoding="utf-8") == "figure"
    assert (build_dir / "other.pdf").read_text(encoding="utf-8") == "other"
    assert not (source_dir / "main.pdf").exists()
    assert not (source_dir / "main.aux").exists()
    assert not (out_dir / "main.synctex.gz").exists()


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
            "out/book/main.pdf",
            "build/book/main.aux",
        ],
        cwd=ROOT,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    output = result.stdout + result.stderr
    assert "src/**/*.tex" in output
    assert "out/*" in output
    assert "build/*" in output
