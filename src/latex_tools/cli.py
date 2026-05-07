"""CLI entry point for latex-tools."""

import json
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from .extract.base import ImageRenderOptions
from .llm.cache import ChunkCacheOptions
from .llm.client import OpenAICompatibleClient
from .llm.config import LLMConfig, LLMConfigError
from .llm.pipeline import LLMPdfConverter
from .llm.presets import (
    DEFAULT_PROMPT_PRESET_NAME,
    PromptPreset,
    PromptPresetError,
    build_prompt_preset_from_inputs,
    list_prompt_presets,
    load_prompt_preset,
    save_prompt_preset,
)


class TitleSource(str, Enum):
    """Document title source strategy."""

    filename = "filename"
    llm = "llm"


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
presets_app = typer.Typer(help="Manage prompt presets.")
app.add_typer(presets_app, name="presets")


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
    timeout: Optional[float],
    max_tokens: int,
    chunk_pages: int,
    image_dpi: int,
    image_dpi_min: int = 100,
    image_dpi_max: Optional[int] = None,
    image_format: str = "png",
    jpeg_quality: int = 85,
    prefetch_chunks: int = 1,
    cache_dir: Path = Path("build/.latex_tools_cache"),
    no_cache: bool = False,
    clear_cache: bool = False,
    extra_prompt: Optional[str] = None,
    preset: str = DEFAULT_PROMPT_PRESET_NAME,
    prompt_preset: Optional[PromptPreset] = None,
    title_source: TitleSource | str = TitleSource.filename,
    manual_title: Optional[str] = None,
    show_date: bool = False,
    client: Optional[OpenAICompatibleClient] = None,
) -> LLMPdfConverter:
    try:
        resolved_title_source = (
            title_source.value if isinstance(title_source, TitleSource) else str(title_source)
        )
        if resolved_title_source not in {TitleSource.filename.value, TitleSource.llm.value}:
            raise ValueError("--title-source must be filename or llm.")
        resolved_manual_title = None
        if manual_title is not None:
            resolved_manual_title = manual_title.strip()
            if not resolved_manual_title:
                raise ValueError("--title cannot be empty.")
        if resolved_manual_title is not None and resolved_title_source == TitleSource.llm.value:
            raise ValueError("--title cannot be used with --title-source llm.")

        config = LLMConfig.from_values(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        image_options = ImageRenderOptions(
            dpi=image_dpi,
            dpi_min=image_dpi_min,
            dpi_max=image_dpi if image_dpi_max is None else image_dpi_max,
            image_format=image_format,
            jpeg_quality=jpeg_quality,
        )
        if prefetch_chunks < 0:
            raise ValueError("prefetch_chunks must be non-negative.")
        if no_cache and clear_cache:
            raise ValueError("--clear-cache cannot be used with --no-cache.")
        resolved_prompt_preset = prompt_preset or load_prompt_preset(
            preset,
            repo_root=_repo_root(),
        )
    except (LLMConfigError, PromptPresetError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    llm_client = client or OpenAICompatibleClient(config)
    cache_options = None
    if not no_cache:
        cache_options = ChunkCacheOptions(
            cache_dir=_resolve_output_dir(cache_dir),
            clear=clear_cache,
            llm_model=config.model,
            llm_base_url=config.base_url,
            llm_temperature=config.temperature,
            llm_max_tokens=config.max_tokens,
        )
    return LLMPdfConverter(
        llm_client,
        chunk_pages=chunk_pages,
        image_dpi=image_dpi,
        image_options=image_options,
        prefetch_chunks=prefetch_chunks,
        cache_options=cache_options,
        extra_prompt=extra_prompt or "",
        prompt_preset=resolved_prompt_preset,
        title_source=resolved_title_source,
        manual_title=resolved_manual_title,
        show_date=show_date,
    )


def _load_cli_prompt_preset(name: str) -> PromptPreset:
    try:
        return load_prompt_preset(name, repo_root=_repo_root())
    except PromptPresetError as exc:
        raise typer.BadParameter(str(exc)) from exc


@presets_app.command("list")
def presets_list():
    """List built-in and repository-local prompt presets."""
    try:
        items = list_prompt_presets(repo_root=_repo_root())
    except PromptPresetError as exc:
        raise typer.BadParameter(str(exc)) from exc

    for item in items:
        location = item.source
        typer.echo(f"{item.preset.name}\t{location}\t{item.preset.description}")


@presets_app.command("show")
def presets_show(
    name: str = typer.Argument(..., help="Prompt preset name"),
):
    """Show one prompt preset as JSON."""
    preset = _load_cli_prompt_preset(name)
    typer.echo(
        json.dumps(
            preset.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


@presets_app.command("add")
def presets_add(
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="New preset name, e.g. chinese-math-lite",
    ),
    from_preset: str = typer.Option(
        DEFAULT_PROMPT_PRESET_NAME,
        "--from-preset",
        help="Existing preset to copy before applying interactive instructions",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Replace an existing repository-local preset with the same name",
    ),
):
    """Interactively add a repository-local prompt preset."""
    try:
        base_preset = load_prompt_preset(from_preset, repo_root=_repo_root())
    except PromptPresetError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo("创建 Prompt 预设。直接回车表示沿用当前基础预设。")
    preset_name = (name or typer.prompt("预设名称（小写英文、数字、- 或 _）")).strip()
    description = str(
        typer.prompt(
            "简短说明",
            default=f"{base_preset.description} 自定义版",
        )
    ).strip()
    chunk_rule = str(
        typer.prompt(
            "正文整理规则",
            default="",
            show_default=False,
        )
    ).strip()
    chunk_context = str(
        typer.prompt(
            "分块输入说明",
            default="",
            show_default=False,
        )
    ).strip()
    title_rule = str(
        typer.prompt(
            "标题生成规则",
            default="",
            show_default=False,
        )
    ).strip()
    preset_extra = str(
        typer.prompt(
            "默认额外说明",
            default="",
            show_default=False,
        )
    ).strip()

    try:
        preset = build_prompt_preset_from_inputs(
            name=preset_name,
            description=description,
            base_preset=base_preset,
            chunk_rule=chunk_rule,
            chunk_context=chunk_context,
            title_rule=title_rule,
            extra_prompt=preset_extra,
        )
        path = save_prompt_preset(
            preset,
            repo_root=_repo_root(),
            overwrite=overwrite,
        )
    except PromptPresetError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"已保存预设：{path}")


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
    title: Optional[str] = typer.Option(
        None,
        "--title",
        help="Manual LaTeX document title for this single PDF",
    ),
    title_source: TitleSource = typer.Option(
        TitleSource.filename,
        "--title-source",
        case_sensitive=False,
        help="Title source: filename or llm",
    ),
    show_date: bool = typer.Option(
        False,
        "--show-date/--hide-date",
        help="Show \\today in the generated LaTeX title block",
    ),
    preset: str = typer.Option(
        DEFAULT_PROMPT_PRESET_NAME,
        "--preset",
        help="Prompt preset name",
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
    timeout: Optional[float] = typer.Option(
        None,
        "--timeout",
        help="LLM request read timeout in seconds (default: wait indefinitely)",
    ),
    max_tokens: int = typer.Option(
        128000, "--max-tokens", help="Maximum tokens in LLM response"
    ),
    chunk_pages: int = typer.Option(
        4, "--chunk-pages", help="Number of pages per LLM request"
    ),
    image_dpi: int = typer.Option(
        160, "--image-dpi", help="Render DPI for page images"
    ),
    image_dpi_min: int = typer.Option(
        100, "--image-dpi-min", help="Minimum render DPI for auto image mode"
    ),
    image_dpi_max: Optional[int] = typer.Option(
        None,
        "--image-dpi-max",
        help="Maximum render DPI for auto image mode (default: --image-dpi)",
    ),
    image_format: str = typer.Option(
        "png", "--image-format", help="Image format: png, jpeg, jpg, or auto"
    ),
    jpeg_quality: int = typer.Option(
        85, "--jpeg-quality", help="JPEG quality for rendered page images"
    ),
    prefetch_chunks: int = typer.Option(
        1, "--prefetch-chunks", help="Number of future chunks to pre-render"
    ),
    cache_dir: Path = typer.Option(
        Path("build/.latex_tools_cache"),
        "--cache-dir",
        help="Directory for resumable chunk cache",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable resumable chunk cache",
    ),
    clear_cache: bool = typer.Option(
        False,
        "--clear-cache",
        help="Clear matching chunk cache before conversion",
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
        image_dpi_min=image_dpi_min,
        image_dpi_max=image_dpi_max,
        image_format=image_format,
        jpeg_quality=jpeg_quality,
        prefetch_chunks=prefetch_chunks,
        cache_dir=cache_dir,
        no_cache=no_cache,
        clear_cache=clear_cache,
        extra_prompt=extra_prompt,
        preset=preset,
        title_source=title_source,
        manual_title=title,
        show_date=show_date,
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
    title_source: TitleSource = typer.Option(
        TitleSource.filename,
        "--title-source",
        case_sensitive=False,
        help="Title source: filename or llm",
    ),
    show_date: bool = typer.Option(
        False,
        "--show-date/--hide-date",
        help="Show \\today in the generated LaTeX title block",
    ),
    preset: str = typer.Option(
        DEFAULT_PROMPT_PRESET_NAME,
        "--preset",
        help="Prompt preset name",
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
    timeout: Optional[float] = typer.Option(
        None,
        "--timeout",
        help="LLM request read timeout in seconds (default: wait indefinitely)",
    ),
    max_tokens: int = typer.Option(
        128000, "--max-tokens", help="Maximum tokens in LLM response"
    ),
    chunk_pages: int = typer.Option(
        4, "--chunk-pages", help="Number of pages per LLM request"
    ),
    image_dpi: int = typer.Option(
        160, "--image-dpi", help="Render DPI for page images"
    ),
    image_dpi_min: int = typer.Option(
        100, "--image-dpi-min", help="Minimum render DPI for auto image mode"
    ),
    image_dpi_max: Optional[int] = typer.Option(
        None,
        "--image-dpi-max",
        help="Maximum render DPI for auto image mode (default: --image-dpi)",
    ),
    image_format: str = typer.Option(
        "png", "--image-format", help="Image format: png, jpeg, jpg, or auto"
    ),
    jpeg_quality: int = typer.Option(
        85, "--jpeg-quality", help="JPEG quality for rendered page images"
    ),
    prefetch_chunks: int = typer.Option(
        1, "--prefetch-chunks", help="Number of future chunks to pre-render"
    ),
    cache_dir: Path = typer.Option(
        Path("build/.latex_tools_cache"),
        "--cache-dir",
        help="Directory for resumable chunk cache",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable resumable chunk cache",
    ),
    clear_cache: bool = typer.Option(
        False,
        "--clear-cache",
        help="Clear matching chunk cache before conversion",
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
        image_dpi_min=image_dpi_min,
        image_dpi_max=image_dpi_max,
        image_format=image_format,
        jpeg_quality=jpeg_quality,
        prefetch_chunks=prefetch_chunks,
        cache_dir=cache_dir,
        no_cache=no_cache,
        clear_cache=clear_cache,
        extra_prompt=extra_prompt,
        preset=preset,
        title_source=title_source,
        show_date=show_date,
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
