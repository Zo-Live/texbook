"""Persistent cache for LLM-generated structure plans and LaTeX chunks."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from ..document_class import DocumentClassResult, LatexDocumentClass
from ..extract.base import ImageRenderOptions, PdfDocumentChunk, PdfPageContext
from ..latex_text import normalize_latex_fragment_newlines
from ..output_options import DEFAULT_OUTPUT_OPTIONS, LatexOutputOptions
from ..structure import (
    StructureEvidence,
    StructurePlan,
    StructurePlannerOptions,
    plan_hash_payload,
)
from .client import (
    LLMChunkResult,
    LLMDocumentClassResult,
    LLMStructurePlanResult,
)
from .prompts import DOCUMENT_CLASS_SYSTEM_PROMPT, STRUCTURE_SYSTEM_PROMPT
from .presets import PromptPreset, default_prompt_preset


CACHE_SCHEMA_VERSION = 1
PROMPT_CACHE_VERSION = 6
STRUCTURE_CACHE_VERSION = 1

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
        document_class: LatexDocumentClass = LatexDocumentClass.ctexart,
        output_options: LatexOutputOptions | None = None,
    ):
        self.options = options
        self.document_title = document_title
        self.prompt_preset = prompt_preset or default_prompt_preset()
        self.title_source = title_source
        self.structure_plan = structure_plan
        self.document_class = document_class
        self.output_options = output_options or DEFAULT_OUTPUT_OPTIONS
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
            document_class=document_class,
            output_options=self.output_options,
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
            latex=normalize_latex_fragment_newlines(latex),
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
            "document_class": self.document_class.value,
            "output_options": self.output_options.to_metadata(),
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
            and data.get("document_class") == self.document_class.value
            and data.get("output_options") == self.output_options.to_metadata()
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


class StructurePlanCacheRun:
    """Cache namespace for one PDF structure-planning run."""

    def __init__(
        self,
        *,
        options: ChunkCacheOptions,
        pdf_path: Path,
        pages: Sequence[int] | None,
        document_title: str,
        image_dpi: int,
        image_options: ImageRenderOptions,
        extra_prompt: str,
        structure_options: StructurePlannerOptions,
        evidence: StructureEvidence,
    ):
        self.options = options
        self.document_title = document_title
        self.evidence = evidence
        self.structure_options = structure_options
        self.run_key = _structure_run_key(
            options=options,
            pdf_path=pdf_path,
            pages=pages,
            document_title=document_title,
            image_dpi=image_dpi,
            image_options=image_options,
            extra_prompt=extra_prompt,
            structure_options=structure_options,
            evidence=evidence,
        )
        self.run_dir = options.cache_dir / self.run_key / "structure"
        if options.clear:
            self.clear()

    def clear(self) -> None:
        """Remove cached structure-planning entries for this run."""
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def write_evidence(self) -> None:
        """Persist local evidence for inspection."""
        self._write_json(
            self.run_dir / "evidence.json",
            {
                "schema_version": CACHE_SCHEMA_VERSION,
                "structure_cache_version": STRUCTURE_CACHE_VERSION,
                "run_key": self.run_key,
                "evidence": self.evidence.to_metadata(),
            },
        )

    def write_local_plan(
        self,
        plan: StructurePlan,
        *,
        filename: str = "structure-local.json",
    ) -> None:
        """Persist a locally resolved structure plan for inspection."""
        self._write_json(
            self.run_dir / filename,
            {
                "schema_version": CACHE_SCHEMA_VERSION,
                "structure_cache_version": STRUCTURE_CACHE_VERSION,
                "run_key": self.run_key,
                "kind": "local-plan",
                "plan": plan.to_metadata(),
            },
        )

    def read(
        self,
        *,
        stage: str,
        request_index: int,
        pages: Sequence[PdfPageContext],
        inspected_pages: Sequence[int],
    ) -> LLMStructurePlanResult | None:
        """Return a cached LLM structure-planning result when valid."""
        path = self._structure_path(stage=stage, request_index=request_index)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict) or not self._matches_structure_entry(
            data,
            stage=stage,
            request_index=request_index,
            pages=pages,
            inspected_pages=inspected_pages,
        ):
            return None

        result_value = data.get("result")
        if not isinstance(result_value, dict):
            return None
        try:
            normalized_plan = data.get("normalized_plan")
            if isinstance(normalized_plan, dict):
                StructurePlan.from_metadata(normalized_plan)
            return _structure_result_from_payload(result_value)
        except (TypeError, ValueError):
            return None

    def write(
        self,
        *,
        stage: str,
        request_index: int,
        pages: Sequence[PdfPageContext],
        inspected_pages: Sequence[int],
        result: LLMStructurePlanResult,
        normalized_plan: StructurePlan | None = None,
    ) -> None:
        """Persist one successfully received structure-planning response."""
        payload = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "structure_cache_version": STRUCTURE_CACHE_VERSION,
            "run_key": self.run_key,
            "document_title": self.document_title,
            "stage": stage,
            "request_index": request_index,
            "page_numbers": _page_context_numbers(pages),
            "inspected_pages": _normalize_pages(inspected_pages),
            "page_text_sha256": _sha256_text(_structure_pages_text(pages)),
            "evidence_sha256": _metadata_sha256(self.evidence.to_metadata()),
            "structure_prompt_sha256": _sha256_text(STRUCTURE_SYSTEM_PROMPT),
            "result": _structure_result_payload(result),
            "normalized_plan": (
                normalized_plan.to_metadata() if normalized_plan is not None else None
            ),
        }
        self._write_json(
            self._structure_path(stage=stage, request_index=request_index),
            payload,
        )

    def _structure_path(self, *, stage: str, request_index: int) -> Path:
        safe_stage = "".join(
            char if char.isalnum() or char in {"-", "_"} else "-"
            for char in stage.strip().lower()
        ) or "stage"
        return self.run_dir / f"structure-{safe_stage}-{request_index:02d}.json"

    def _matches_structure_entry(
        self,
        data: dict[str, Any],
        *,
        stage: str,
        request_index: int,
        pages: Sequence[PdfPageContext],
        inspected_pages: Sequence[int],
    ) -> bool:
        return (
            data.get("schema_version") == CACHE_SCHEMA_VERSION
            and data.get("structure_cache_version") == STRUCTURE_CACHE_VERSION
            and data.get("run_key") == self.run_key
            and data.get("document_title") == self.document_title
            and data.get("stage") == stage
            and data.get("request_index") == request_index
            and data.get("page_numbers") == _page_context_numbers(pages)
            and data.get("inspected_pages") == _normalize_pages(inspected_pages)
            and data.get("page_text_sha256") == _sha256_text(_structure_pages_text(pages))
            and data.get("evidence_sha256")
            == _metadata_sha256(self.evidence.to_metadata())
            and data.get("structure_prompt_sha256")
            == _sha256_text(STRUCTURE_SYSTEM_PROMPT)
        )

    def _write_json(self, path: Path, data: dict[str, object]) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, data, directory=self.run_dir)


class DocumentClassCacheRun:
    """Cache namespace for one PDF document-class decision."""

    def __init__(
        self,
        *,
        options: ChunkCacheOptions,
        pdf_path: Path,
        pages: Sequence[int] | None,
        document_title: str,
        image_dpi: int,
        image_options: ImageRenderOptions,
        extra_prompt: str,
        evidence: StructureEvidence,
    ):
        self.options = options
        self.document_title = document_title
        self.evidence = evidence
        self.run_key = _document_class_run_key(
            options=options,
            pdf_path=pdf_path,
            pages=pages,
            document_title=document_title,
            image_dpi=image_dpi,
            image_options=image_options,
            extra_prompt=extra_prompt,
            evidence=evidence,
        )
        self.run_dir = options.cache_dir / self.run_key / "document-class"
        if options.clear:
            self.clear()

    def clear(self) -> None:
        """Remove cached document-class entries for this run."""
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def read(
        self,
        *,
        pages: Sequence[PdfPageContext],
    ) -> LLMDocumentClassResult | None:
        """Return a cached document-class result when valid."""
        path = self.run_dir / "document-class.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or not self._matches_entry(data, pages=pages):
            return None
        result_value = data.get("result")
        if not isinstance(result_value, dict):
            return None
        try:
            result = _document_class_result_from_payload(result_value)
            result.normalized()
        except (TypeError, ValueError):
            return None
        return result

    def write(
        self,
        *,
        pages: Sequence[PdfPageContext],
        result: LLMDocumentClassResult,
        normalized_result: DocumentClassResult | None = None,
    ) -> None:
        """Persist a successfully received document-class response."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(
            self.run_dir / "document-class.json",
            {
                "schema_version": CACHE_SCHEMA_VERSION,
                "structure_cache_version": STRUCTURE_CACHE_VERSION,
                "run_key": self.run_key,
                "document_title": self.document_title,
                "page_numbers": _page_context_numbers(pages),
                "page_text_sha256": _sha256_text(_structure_pages_text(pages)),
                "evidence_sha256": _metadata_sha256(self.evidence.to_metadata()),
                "document_class_prompt_sha256": _sha256_text(
                    DOCUMENT_CLASS_SYSTEM_PROMPT
                ),
                "result": _document_class_result_payload(result),
                "normalized_result": (
                    normalized_result.to_metadata()
                    if normalized_result is not None
                    else None
                ),
            },
            directory=self.run_dir,
        )

    def _matches_entry(
        self,
        data: dict[str, Any],
        *,
        pages: Sequence[PdfPageContext],
    ) -> bool:
        return (
            data.get("schema_version") == CACHE_SCHEMA_VERSION
            and data.get("structure_cache_version") == STRUCTURE_CACHE_VERSION
            and data.get("run_key") == self.run_key
            and data.get("document_title") == self.document_title
            and data.get("page_numbers") == _page_context_numbers(pages)
            and data.get("page_text_sha256") == _sha256_text(_structure_pages_text(pages))
            and data.get("evidence_sha256")
            == _metadata_sha256(self.evidence.to_metadata())
            and data.get("document_class_prompt_sha256")
            == _sha256_text(DOCUMENT_CLASS_SYSTEM_PROMPT)
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
    document_class: LatexDocumentClass = LatexDocumentClass.ctexart,
    output_options: LatexOutputOptions | None = None,
) -> str:
    resolved_prompt_preset = prompt_preset or default_prompt_preset()
    resolved_output_options = output_options or DEFAULT_OUTPUT_OPTIONS
    payload = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "prompt_cache_version": PROMPT_CACHE_VERSION,
        "pdf_sha256": _sha256_file(pdf_path),
        "document_title": document_title,
        "title_source": title_source,
        "document_class": document_class.value,
        "output_options": resolved_output_options.to_metadata(),
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


def _structure_run_key(
    *,
    options: ChunkCacheOptions,
    pdf_path: Path,
    pages: Sequence[int] | None,
    document_title: str,
    image_dpi: int,
    image_options: ImageRenderOptions,
    extra_prompt: str,
    structure_options: StructurePlannerOptions,
    evidence: StructureEvidence,
) -> str:
    payload = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "structure_cache_version": STRUCTURE_CACHE_VERSION,
        "pdf_sha256": _sha256_file(pdf_path),
        "document_title": document_title,
        "pages": _normalize_pages(pages),
        "image_dpi": image_dpi,
        "image_options": _image_options_payload(image_options),
        "extra_prompt": extra_prompt,
        "structure_options": _structure_options_payload(structure_options),
        "structure_prompt_sha256": _sha256_text(STRUCTURE_SYSTEM_PROMPT),
        "evidence": evidence.to_metadata(),
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


def _document_class_run_key(
    *,
    options: ChunkCacheOptions,
    pdf_path: Path,
    pages: Sequence[int] | None,
    document_title: str,
    image_dpi: int,
    image_options: ImageRenderOptions,
    extra_prompt: str,
    evidence: StructureEvidence,
) -> str:
    payload = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "structure_cache_version": STRUCTURE_CACHE_VERSION,
        "pdf_sha256": _sha256_file(pdf_path),
        "document_title": document_title,
        "pages": _normalize_pages(pages),
        "image_dpi": image_dpi,
        "image_options": _image_options_payload(image_options),
        "extra_prompt": extra_prompt,
        "document_class_prompt_sha256": _sha256_text(DOCUMENT_CLASS_SYSTEM_PROMPT),
        "evidence": evidence.to_metadata(),
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


def _normalize_page_value(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    pages: list[int] = []
    for item in value:
        if isinstance(item, bool):
            continue
        try:
            page = int(item)
        except (TypeError, ValueError):
            continue
        if page > 0:
            pages.append(page)
    return sorted(set(pages))


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


def _structure_options_payload(options: StructurePlannerOptions) -> dict[str, int | str]:
    return {
        "mode": options.mode.value,
        "chunk_pages": options.chunk_pages,
        "max_pages": options.max_pages,
    }


def _page_context_numbers(pages: Sequence[PdfPageContext]) -> list[int]:
    return [page.page_number for page in pages]


def _structure_pages_text(pages: Sequence[PdfPageContext]) -> str:
    lines: list[str] = []
    for page in pages:
        lines.append(f"PAGE {page.page_number}")
        lines.append(f"{page.width:.2f}x{page.height:.2f}")
        for block in page.text_blocks:
            bbox = ",".join(f"{value:.1f}" for value in block.bbox)
            lines.append(
                f"{bbox}|{block.font_size:.1f}|{block.block_type}|{block.text}"
            )
    return "\n".join(lines)


def _metadata_sha256(data: dict[str, object]) -> str:
    raw_payload = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw_payload).hexdigest()


def _structure_result_payload(result: LLMStructurePlanResult) -> dict[str, object]:
    return {
        "status": result.status,
        "plan": list(result.plan),
        "confidence": result.confidence,
        "reason": result.reason,
        "needed_pages": list(result.needed_pages),
        "notes": list(result.notes),
    }


def _structure_result_from_payload(data: dict[str, Any]) -> LLMStructurePlanResult:
    status = str(data.get("status", "")).strip().lower()
    if status not in {"complete", "need_more", "insufficient"}:
        raise ValueError("cached structure result status is invalid.")
    plan_value = data.get("plan", [])
    if not isinstance(plan_value, list):
        raise ValueError("cached structure result plan must be a list.")
    needed_pages = _normalize_page_value(data.get("needed_pages", []))
    notes_value = data.get("notes", [])
    notes = (
        [str(note) for note in notes_value if str(note).strip()]
        if isinstance(notes_value, list)
        else []
    )
    return LLMStructurePlanResult(
        status=status,
        plan=[
            dict(item)
            for item in plan_value
            if isinstance(item, dict)
        ],
        confidence=_coerce_float(data.get("confidence")),
        reason=str(data.get("reason", "")).strip(),
        needed_pages=needed_pages,
        notes=notes,
    )


def _document_class_result_payload(
    result: LLMDocumentClassResult,
) -> dict[str, object]:
    return {
        "document_class": result.document_class,
        "confidence": result.confidence,
        "reason": result.reason,
        "notes": list(result.notes),
    }


def _document_class_result_from_payload(
    data: dict[str, Any],
) -> LLMDocumentClassResult:
    document_class = str(data.get("document_class", "")).strip().lower()
    if not document_class:
        raise ValueError("cached document-class result is missing document_class.")
    notes_value = data.get("notes", [])
    notes = (
        [str(note) for note in notes_value if str(note).strip()]
        if isinstance(notes_value, list)
        else []
    )
    return LLMDocumentClassResult(
        document_class=document_class,
        confidence=_coerce_float(data.get("confidence")),
        reason=str(data.get("reason", "")).strip(),
        notes=notes,
    )


def _coerce_float(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return min(1.0, max(0.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _write_json_atomic(path: Path, data: dict[str, object], *, directory: Path) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=directory,
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
