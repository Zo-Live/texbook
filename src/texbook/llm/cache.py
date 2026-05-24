"""Persistent cache for LLM-generated LaTeX chunks."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from ..extract.base import ImageRenderOptions, PdfDocumentChunk
from ..structure import StructurePlan, plan_hash_payload
from .client import LLMChunkResult
from .presets import PromptPreset, default_prompt_preset


CACHE_SCHEMA_VERSION = 1
PROMPT_CACHE_VERSION = 2

_HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class ChunkCacheOptions:
    """Runtime options for chunk result caching."""

    enabled: bool = True
    cache_dir: Path = Path("build/.texbook_cache")
    clear: bool = False
    llm_model: str = ""
    llm_base_url: str | None = None
    llm_temperature: float = 1.0
    llm_max_tokens: int = 128000

    def __post_init__(self) -> None:
        object.__setattr__(self, "cache_dir", Path(self.cache_dir))


class ChunkCacheRun:
    """Cache namespace for one PDF conversion run."""

    def __init__(
        self,
        *,
        options: ChunkCacheOptions,
        pdf_path: Path,
        pages: Sequence[int] | None,
        document_title: str,
        chunk_pages: int,
        image_dpi: int,
        image_options: ImageRenderOptions,
        extra_prompt: str,
        prompt_preset: PromptPreset | None = None,
        title_source: str = "filename",
        structure_plan: StructurePlan | None = None,
    ):
        self.options = options
        self.document_title = document_title
        self.prompt_preset = prompt_preset or default_prompt_preset()
        self.title_source = title_source
        self.structure_plan = structure_plan
        self.run_key = _run_key(
            options=options,
            pdf_path=pdf_path,
            pages=pages,
            document_title=document_title,
            chunk_pages=chunk_pages,
            image_dpi=image_dpi,
            image_options=image_options,
            extra_prompt=extra_prompt,
            prompt_preset=self.prompt_preset,
            title_source=title_source,
            structure_plan=structure_plan,
        )
        self.run_dir = options.cache_dir / self.run_key
        if options.clear:
            self.clear()

    def clear(self) -> None:
        """Remove cached chunks for this run."""
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def read(
        self,
        chunk: PdfDocumentChunk,
        previous_latex_tail: str,
    ) -> LLMChunkResult | None:
        """Return a cached chunk result when the entry is valid."""
        path = self._chunk_path(chunk)
        if not path.is_file():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict) or not self._matches_entry(
            data,
            chunk=chunk,
            previous_latex_tail=previous_latex_tail,
        ):
            return None

        latex = data.get("latex")
        notes = data.get("notes")
        if not isinstance(latex, str) or not latex.strip():
            return None
        if not isinstance(notes, list):
            return None

        return LLMChunkResult(
            latex=latex,
            notes=[str(note) for note in notes if str(note).strip()],
        )

    def write(
        self,
        chunk: PdfDocumentChunk,
        previous_latex_tail: str,
        result: LLMChunkResult,
    ) -> None:
        """Persist one successfully generated chunk result."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self._chunk_path(chunk)
        data = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "prompt_cache_version": PROMPT_CACHE_VERSION,
            "run_key": self.run_key,
            "document_title": self.document_title,
            "title_source": self.title_source,
            "structure_plan": plan_hash_payload(self.structure_plan),
            "prompt_preset_name": self.prompt_preset.name,
            "prompt_preset_version": self.prompt_preset.version,
            "prompt_preset_hash": self.prompt_preset.prompt_hash(),
            "chunk_index": chunk.chunk_index,
            "total_chunks": chunk.total_chunks,
            "page_numbers": _chunk_page_numbers(chunk),
            "previous_latex_tail_sha256": _sha256_text(previous_latex_tail),
            "latex": result.latex,
            "notes": list(result.notes),
        }

        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.run_dir,
                prefix=f"{path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(
                    data,
                    temp_file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                temp_file.write("\n")
            temp_path.replace(path)
        except Exception:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise

    def _chunk_path(self, chunk: PdfDocumentChunk) -> Path:
        return self.run_dir / f"chunk-{chunk.chunk_index:04d}.json"

    def _matches_entry(
        self,
        data: dict[str, Any],
        *,
        chunk: PdfDocumentChunk,
        previous_latex_tail: str,
    ) -> bool:
        return (
            data.get("schema_version") == CACHE_SCHEMA_VERSION
            and data.get("prompt_cache_version") == PROMPT_CACHE_VERSION
            and data.get("run_key") == self.run_key
            and data.get("document_title") == self.document_title
            and data.get("title_source") == self.title_source
            and data.get("structure_plan") == plan_hash_payload(self.structure_plan)
            and data.get("prompt_preset_name") == self.prompt_preset.name
            and data.get("prompt_preset_version") == self.prompt_preset.version
            and data.get("prompt_preset_hash") == self.prompt_preset.prompt_hash()
            and data.get("chunk_index") == chunk.chunk_index
            and data.get("total_chunks") == chunk.total_chunks
            and data.get("page_numbers") == _chunk_page_numbers(chunk)
            and data.get("previous_latex_tail_sha256")
            == _sha256_text(previous_latex_tail)
        )


def _run_key(
    *,
    options: ChunkCacheOptions,
    pdf_path: Path,
    pages: Sequence[int] | None,
    document_title: str,
    chunk_pages: int,
    image_dpi: int,
    image_options: ImageRenderOptions,
    extra_prompt: str,
    prompt_preset: PromptPreset | None = None,
    title_source: str = "filename",
    structure_plan: StructurePlan | None = None,
) -> str:
    resolved_prompt_preset = prompt_preset or default_prompt_preset()
    payload = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "prompt_cache_version": PROMPT_CACHE_VERSION,
        "pdf_sha256": _sha256_file(pdf_path),
        "document_title": document_title,
        "title_source": title_source,
        "structure_plan": plan_hash_payload(structure_plan),
        "pages": _normalize_pages(pages),
        "chunk_pages": chunk_pages,
        "image_dpi": image_dpi,
        "image_options": _image_options_payload(image_options),
        "extra_prompt": extra_prompt,
        "prompt_preset": {
            "name": resolved_prompt_preset.name,
            "version": resolved_prompt_preset.version,
            "hash": resolved_prompt_preset.prompt_hash(),
        },
        "llm": {
            "model": options.llm_model,
            "base_url": options.llm_base_url,
            "temperature": options.llm_temperature,
            "max_tokens": options.llm_max_tokens,
        },
    }
    raw_payload = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw_payload).hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(_HASH_CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_pages(pages: Sequence[int] | None) -> list[int] | None:
    if pages is None:
        return None
    return sorted({int(page) for page in pages})


def _image_options_payload(options: ImageRenderOptions) -> dict[str, int | str]:
    return {
        "dpi": options.dpi,
        "dpi_min": options.dpi_min,
        "dpi_max": options.dpi_max,
        "image_format": options.image_format,
        "jpeg_quality": options.jpeg_quality,
    }


def _chunk_page_numbers(chunk: PdfDocumentChunk) -> list[int]:
    return [page.page_number for page in chunk.pages]
