"""CLI entry point for latex-tools."""

from pathlib import Path
from typing import Optional

import typer

from .extract.text_extractor import TextExtractor
from .convert.latex_converter import LatexConverter


def _repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "latex_tools"
        ).is_dir():
            return candidate
    return cwd


def _resolve_existing_path(path: Path) -> Path:
    path = path.expanduser()
    candidates = [path] if path.is_absolute() else [Path.cwd() / path, _repo_root() / path]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise typer.BadParameter(f"Path does not exist: {path}")


def _resolve_tex_output(path: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path

    root = _repo_root()
    if path.parent == Path("."):
        return root / "src" / path
    return root / path


def _resolve_output_dir(path: Path) -> Path:
    path = path.expanduser()
    return path if path.is_absolute() else _repo_root() / path


app = typer.Typer(
    name="latex-tools",
    help="Extract content from PDFs and convert to LaTeX source.",
)


@app.command()
def extract(
    pdf_path: Path = typer.Argument(
        ...,
        help="Path to the PDF file to extract",
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="Output .tex file path (default: stdout)"
    ),
):
    """Extract content from a single PDF and convert to LaTeX."""
    pdf_path = _resolve_existing_path(pdf_path)
    if not pdf_path.is_file():
        raise typer.BadParameter(f"Not a file: {pdf_path}")

    extractor = TextExtractor()
    content = extractor.extract(pdf_path)
    converter = LatexConverter()
    latex = converter.convert(content)

    if output:
        output = _resolve_tex_output(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(latex, encoding="utf-8")
        typer.echo(f"Written to {output}", err=True)
    else:
        typer.echo(latex)


@app.command()
def batch(
    directory: Path = typer.Argument(
        ...,
        help="Directory containing PDF files",
        file_okay=False,
        dir_okay=True,
    ),
    output_dir: Path = typer.Option(
        Path("src"), "-o", "--output-dir", help="Directory to write .tex files to"
    ),
    pattern: str = typer.Option(
        "*.pdf", "--pattern", help="Glob pattern for PDF files"
    ),
):
    """Extract all matching PDFs in a directory to individual .tex files."""
    directory = _resolve_existing_path(directory)
    if not directory.is_dir():
        raise typer.BadParameter(f"Not a directory: {directory}")

    extractor = TextExtractor()
    converter = LatexConverter()
    output_dir = _resolve_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(Path(directory).glob(pattern))
    if not pdf_files:
        typer.echo(f"No PDFs found matching '{pattern}' in {directory}", err=True)
        raise typer.Exit(1)

    for pdf in pdf_files:
        typer.echo(f"Processing: {pdf.name}", err=True)
        content = extractor.extract(pdf)
        latex = converter.convert(content)
        tex_path = output_dir / f"{pdf.stem}.tex"
        tex_path.write_text(latex, encoding="utf-8")

    typer.echo(f"Done. {len(pdf_files)} files written to {output_dir}", err=True)


if __name__ == "__main__":
    app()
