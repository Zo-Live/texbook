"""CLI entry point for latex-tools."""

from pathlib import Path
from typing import Optional

import typer

from .llm.client import OpenAICompatibleClient
from .llm.config import LLMConfig, LLMConfigError
from .llm.pipeline import LLMPdfConverter


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
    help="Convert PDFs to LaTeX source using an LLM-assisted pipeline.",
)


def _parse_pages(pages: Optional[str]) -> Optional[list[int]]:
    if pages is None or not pages.strip():
        return None

    resolved: list[int] = []
    for chunk in pages.split(","):
        item = chunk.strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start = int(start_text.strip())
            end = int(end_text.strip())
            if start <= 0 or end <= 0 or end < start:
                raise typer.BadParameter(f"Invalid page range: {item}")
            resolved.extend(range(start, end + 1))
        else:
            page = int(item)
            if page <= 0:
                raise typer.BadParameter(f"Invalid page number: {item}")
            resolved.append(page)

    if not resolved:
        raise typer.BadParameter("No valid pages were parsed.")
    seen: set[int] = set()
    unique_pages: list[int] = []
    for page in resolved:
        if page in seen:
            continue
        seen.add(page)
        unique_pages.append(page)
    return unique_pages


def _build_converter(
    *,
    model: Optional[str],
    api_key: Optional[str],
    base_url: Optional[str],
    temperature: float,
    timeout: float,
    max_tokens: int,
    chunk_pages: int,
    image_dpi: int,
    extra_prompt: Optional[str] = None,
    client: Optional[OpenAICompatibleClient] = None,
) -> LLMPdfConverter:
    try:
        config = LLMConfig.from_values(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            timeout=timeout,
            max_tokens=max_tokens,
        )
    except LLMConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc

    llm_client = client or OpenAICompatibleClient(config)
    return LLMPdfConverter(
        llm_client,
        chunk_pages=chunk_pages,
        image_dpi=image_dpi,
        extra_prompt=extra_prompt or "",
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
    pages: Optional[str] = typer.Option(
        None, "--pages", help="Page selection such as 1,3-5 (1-based)"
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        envvar="LATEX_TOOLS_LLM_MODEL",
        help="LLM model name",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="LATEX_TOOLS_LLM_API_KEY",
        help="LLM API key",
        hide_input=True,
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        envvar="LATEX_TOOLS_LLM_BASE_URL",
        help="OpenAI-compatible API base URL",
    ),
    temperature: float = typer.Option(
        1.0, "--temperature", help="Sampling temperature"
    ),
    timeout: float = typer.Option(600.0, "--timeout", help="LLM request read timeout (seconds)"),
    max_tokens: int = typer.Option(
        128000, "--max-tokens", help="Maximum tokens in LLM response"
    ),
    chunk_pages: int = typer.Option(
        4, "--chunk-pages", help="Number of pages per LLM request"
    ),
    image_dpi: int = typer.Option(
        160, "--image-dpi", help="Render DPI for page images"
    ),
    extra_prompt: Optional[str] = typer.Option(
        None, "--extra-prompt", help="额外的系统提示文字（追加到默认要求之后）"
    ),
):
    """Extract content from a single PDF and convert to LaTeX."""
    pdf_path = _resolve_existing_path(pdf_path)
    if not pdf_path.is_file():
        raise typer.BadParameter(f"Not a file: {pdf_path}")

    converter = _build_converter(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        timeout=timeout,
        max_tokens=max_tokens,
        chunk_pages=chunk_pages,
        image_dpi=image_dpi,
        extra_prompt=extra_prompt,
    )
    result = converter.convert(pdf_path, pages=_parse_pages(pages))
    latex = result.latex

    if output:
        output = _resolve_tex_output(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(latex, encoding="utf-8")
        typer.echo(f"Written to {output}", err=True)
    else:
        typer.echo(latex)
    for note in result.notes:
        typer.echo(f"Note: {note}", err=True)


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
    pages: Optional[str] = typer.Option(
        None, "--pages", help="Page selection such as 1,3-5 (1-based)"
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        envvar="LATEX_TOOLS_LLM_MODEL",
        help="LLM model name",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="LATEX_TOOLS_LLM_API_KEY",
        help="LLM API key",
        hide_input=True,
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        envvar="LATEX_TOOLS_LLM_BASE_URL",
        help="OpenAI-compatible API base URL",
    ),
    temperature: float = typer.Option(
        1.0, "--temperature", help="Sampling temperature"
    ),
    timeout: float = typer.Option(600.0, "--timeout", help="LLM request read timeout (seconds)"),
    max_tokens: int = typer.Option(
        128000, "--max-tokens", help="Maximum tokens in LLM response"
    ),
    chunk_pages: int = typer.Option(
        4, "--chunk-pages", help="Number of pages per LLM request"
    ),
    image_dpi: int = typer.Option(
        160, "--image-dpi", help="Render DPI for page images"
    ),
    extra_prompt: Optional[str] = typer.Option(
        None, "--extra-prompt", help="额外的系统提示文字（追加到默认要求之后）"
    ),
):
    """Extract all matching PDFs in a directory to individual .tex files."""
    directory = _resolve_existing_path(directory)
    if not directory.is_dir():
        raise typer.BadParameter(f"Not a directory: {directory}")

    converter = _build_converter(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        timeout=timeout,
        max_tokens=max_tokens,
        chunk_pages=chunk_pages,
        image_dpi=image_dpi,
        extra_prompt=extra_prompt,
    )
    output_dir = _resolve_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    page_selection = _parse_pages(pages)

    pdf_files = sorted(Path(directory).glob(pattern))
    if not pdf_files:
        typer.echo(f"No PDFs found matching '{pattern}' in {directory}", err=True)
        raise typer.Exit(1)

    for pdf in pdf_files:
        typer.echo(f"Processing: {pdf.name}", err=True)
        result = converter.convert(pdf, pages=page_selection)
        latex = result.latex
        tex_path = output_dir / f"{pdf.stem}.tex"
        tex_path.write_text(latex, encoding="utf-8")
        for note in result.notes:
            typer.echo(f"{pdf.name}: {note}", err=True)

    typer.echo(f"Done. {len(pdf_files)} files written to {output_dir}", err=True)


if __name__ == "__main__":
    app()
