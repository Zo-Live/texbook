"""Prompt preset loading and validation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Any


PROMPT_PRESET_SCHEMA_VERSION = 1
DEFAULT_PROMPT_PRESET_NAME = "chinese-math"
REPOSITORY_PRESET_DIR = Path("config/latex_tools/presets")

_PRESET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_HASH_SEPARATORS = (",", ":")


SYSTEM_PROMPT = """你是中文数学讲义的 LaTeX 整理助手。

任务：根据 PDF 页面图像和辅助文本识别结果，重建干净、可编译的 LaTeX 正文片段。

硬性要求：
1. 只输出 JSON 对象，不要输出 Markdown 代码块。
2. JSON 格式必须为 {"latex": "...", "notes": ["..."]}。
3. latex 字段只包含 document 正文内部片段；不要输出 \\documentclass、preamble、\\begin{document} 或 \\end{document}。
4. 忽略重复页眉、页脚、作者、日期、学校名、页码、Beamer 导航信息。
5. Beamer 增量页如果连续重复，只保留最终完整内容，不要重复抄写。
6. 数学内容必须用标准 LaTeX 表达。行内公式用 $...$，独立公式用 \\[...\\] 或 align 环境。
7. 定义、定理、引理、性质、推论、例、证明优先使用 definition、theorem、lemma、property、corollary、example、proof 环境。
8. 不要凭空补充页面中没有的信息；无法确定的内容用 LaTeX 注释 % TODO: 标出。
9. 中文标点和数学符号要尽量还原讲义语义，不要保留 OCR 的逐字断行。
"""

TITLE_SYSTEM_PROMPT = """你是中文数学讲义的标题整理助手。

任务：根据 PDF 文件名、页面文本线索和已生成的 LaTeX 章节线索，生成一个适合作为 LaTeX \\title 的中文标题。

硬性要求：
1. 只输出 JSON 对象，不要输出 Markdown 代码块。
2. JSON 格式必须为 {"title": "..."}。
3. title 要稳定、简短、具体，优先反映讲义主题。
4. 不要包含作者、日期、学校、页码、文件扩展名或“标题：”前缀。
5. 不要凭空补充线索中没有的信息；无法判断时使用文件名中的主题。
"""

CHUNK_USER_TEMPLATE = """文档标题：{document_title}
当前分块：{chunk_index}/{total_chunks}

请把本分块页面整理成连续的 LaTeX 正文片段。
辅助文本识别可能有断行、漏公式、符号误识别；页面图像优先级更高。{previous_latex_tail_section}{pages_text}"""

PAGE_IMAGE_LABEL_TEMPLATE = "下面是第 {page_number} 页的页面图像："

TITLE_USER_TEMPLATE = """默认文件名标题：{fallback_title}

可用标题线索：
{title_evidence}"""


class PromptPresetError(ValueError):
    """Raised when a prompt preset is missing or invalid."""


@dataclass(frozen=True)
class PromptPreset:
    """Complete prompt preset used by the LLM conversion pipeline."""

    name: str
    description: str
    version: str
    chunk_system_prompt: str
    chunk_user_template: str
    page_image_label_template: str
    title_system_prompt: str
    title_user_template: str
    extra_prompt: str = ""
    schema_version: int = PROMPT_PRESET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PROMPT_PRESET_SCHEMA_VERSION:
            raise PromptPresetError(
                f"Unsupported prompt preset schema version: {self.schema_version}"
            )
        validate_prompt_preset_name(self.name)
        _require_text(self.description, "description")
        _require_text(self.version, "version")
        _require_text(self.chunk_system_prompt, "chunk_system_prompt")
        _require_text(self.chunk_user_template, "chunk_user_template")
        _require_text(self.page_image_label_template, "page_image_label_template")
        _require_text(self.title_system_prompt, "title_system_prompt")
        _require_text(self.title_user_template, "title_user_template")
        _validate_template(
            self.chunk_user_template,
            field_name="chunk_user_template",
            allowed_fields={
                "document_title",
                "chunk_index",
                "total_chunks",
                "previous_latex_tail_section",
                "pages_text",
            },
            required_fields={"pages_text"},
            sample_values={
                "document_title": "示例标题",
                "chunk_index": 1,
                "total_chunks": 2,
                "previous_latex_tail_section": "",
                "pages_text": "\n\n--- PAGE 1 ---",
            },
        )
        _validate_template(
            self.page_image_label_template,
            field_name="page_image_label_template",
            allowed_fields={"page_number"},
            required_fields={"page_number"},
            sample_values={"page_number": 1},
        )
        _validate_template(
            self.title_user_template,
            field_name="title_user_template",
            allowed_fields={"fallback_title", "title_evidence"},
            required_fields={"fallback_title", "title_evidence"},
            sample_values={
                "fallback_title": "示例文件",
                "title_evidence": "\\section{示例}",
            },
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptPreset":
        """Build and validate a preset from a JSON-like mapping."""
        if not isinstance(data, dict):
            raise PromptPresetError("Prompt preset JSON must be an object.")

        fields = {
            "schema_version",
            "name",
            "description",
            "version",
            "chunk_system_prompt",
            "chunk_user_template",
            "page_image_label_template",
            "title_system_prompt",
            "title_user_template",
            "extra_prompt",
        }
        missing = sorted(fields - {"extra_prompt"} - set(data))
        if missing:
            raise PromptPresetError(
                "Prompt preset is missing required fields: " + ", ".join(missing)
            )
        unknown = sorted(set(data) - fields)
        if unknown:
            raise PromptPresetError(
                "Prompt preset has unknown fields: " + ", ".join(unknown)
            )

        return cls(
            schema_version=data["schema_version"],
            name=data["name"],
            description=data["description"],
            version=data["version"],
            chunk_system_prompt=data["chunk_system_prompt"],
            chunk_user_template=data["chunk_user_template"],
            page_image_label_template=data["page_image_label_template"],
            title_system_prompt=data["title_system_prompt"],
            title_user_template=data["title_user_template"],
            extra_prompt=data.get("extra_prompt", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-serializable representation."""
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "chunk_system_prompt": self.chunk_system_prompt,
            "chunk_user_template": self.chunk_user_template,
            "page_image_label_template": self.page_image_label_template,
            "title_system_prompt": self.title_system_prompt,
            "title_user_template": self.title_user_template,
            "extra_prompt": self.extra_prompt,
        }

    def prompt_hash(self) -> str:
        """Return a stable hash of all prompt-affecting preset fields."""
        payload = json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=_HASH_SEPARATORS,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PromptPresetInfo:
    """Prompt preset plus source metadata for CLI display."""

    preset: PromptPreset
    source: str
    path: Path | None = None


def default_prompt_preset() -> PromptPreset:
    """Return the built-in default prompt preset."""
    return builtin_prompt_presets()[DEFAULT_PROMPT_PRESET_NAME]


def builtin_prompt_presets() -> dict[str, PromptPreset]:
    """Return all built-in prompt presets."""
    preset = PromptPreset(
        name=DEFAULT_PROMPT_PRESET_NAME,
        description="中文数学讲义默认预设",
        version="1",
        chunk_system_prompt=SYSTEM_PROMPT,
        chunk_user_template=CHUNK_USER_TEMPLATE,
        page_image_label_template=PAGE_IMAGE_LABEL_TEMPLATE,
        title_system_prompt=TITLE_SYSTEM_PROMPT,
        title_user_template=TITLE_USER_TEMPLATE,
    )
    return {preset.name: preset}


def repository_preset_dir(repo_root: Path) -> Path:
    """Return the repository-local preset directory."""
    return Path(repo_root) / REPOSITORY_PRESET_DIR


def validate_prompt_preset_name(name: str) -> str:
    """Validate and normalize a prompt preset name."""
    if not isinstance(name, str):
        raise PromptPresetError("Prompt preset name must be text.")
    normalized = name.strip()
    if not _PRESET_NAME_RE.fullmatch(normalized):
        raise PromptPresetError(
            "Prompt preset name must match "
            "[a-z0-9][a-z0-9_-]{1,63}."
        )
    return normalized


def load_prompt_preset(name: str, *, repo_root: Path) -> PromptPreset:
    """Load a built-in or repository-local prompt preset by name."""
    preset_name = validate_prompt_preset_name(name)
    builtins = builtin_prompt_presets()
    if preset_name in builtins:
        return builtins[preset_name]

    path = repository_preset_dir(repo_root) / f"{preset_name}.json"
    if not path.is_file():
        raise PromptPresetError(f"Unknown prompt preset: {preset_name}")
    preset = load_prompt_preset_file(path)
    if preset.name != preset_name:
        raise PromptPresetError(
            f"Prompt preset file name must match preset name: {path.name}"
        )
    return preset


def load_prompt_preset_file(path: Path) -> PromptPreset:
    """Load one prompt preset JSON file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise PromptPresetError(f"Cannot read prompt preset: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PromptPresetError(f"Prompt preset is not valid JSON: {path}") from exc
    return PromptPreset.from_dict(data)


def list_prompt_presets(*, repo_root: Path) -> list[PromptPresetInfo]:
    """List built-in and repository-local prompt presets."""
    builtins = builtin_prompt_presets()
    items = [
        PromptPresetInfo(preset=preset, source="builtin")
        for preset in builtins.values()
    ]

    preset_dir = repository_preset_dir(repo_root)
    if preset_dir.is_dir():
        for path in sorted(preset_dir.glob("*.json")):
            preset = load_prompt_preset_file(path)
            if preset.name != path.stem:
                raise PromptPresetError(
                    f"Prompt preset file name must match preset name: {path.name}"
                )
            if preset.name in builtins:
                raise PromptPresetError(
                    f"Repository preset cannot override built-in preset: {preset.name}"
                )
            items.append(PromptPresetInfo(preset=preset, source="repo", path=path))

    return sorted(items, key=lambda item: (item.source != "builtin", item.preset.name))


def save_prompt_preset(
    preset: PromptPreset,
    *,
    repo_root: Path,
    overwrite: bool = False,
) -> Path:
    """Save a repository-local prompt preset."""
    if preset.name in builtin_prompt_presets():
        raise PromptPresetError(f"Cannot overwrite built-in preset: {preset.name}")

    preset_dir = repository_preset_dir(repo_root)
    path = preset_dir / f"{preset.name}.json"
    if path.exists() and not overwrite:
        raise PromptPresetError(
            f"Prompt preset already exists: {preset.name}. Use --overwrite to replace it."
        )

    preset_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(
            preset.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
    return path


def build_prompt_preset_from_inputs(
    *,
    name: str,
    description: str,
    base_preset: PromptPreset,
    chunk_rule: str,
    chunk_context: str,
    title_rule: str,
    extra_prompt: str = "",
) -> PromptPreset:
    """Build a full preset from friendly interactive inputs."""
    return PromptPreset(
        name=validate_prompt_preset_name(name),
        description=description.strip(),
        version="1",
        chunk_system_prompt=_append_instruction(
            base_preset.chunk_system_prompt,
            heading="本预设正文整理规则",
            text=chunk_rule,
        ),
        chunk_user_template=_append_instruction(
            base_preset.chunk_user_template,
            heading="本预设分块输入说明",
            text=chunk_context,
            escape_format=True,
        ),
        page_image_label_template=base_preset.page_image_label_template,
        title_system_prompt=_append_instruction(
            base_preset.title_system_prompt,
            heading="本预设标题生成规则",
            text=title_rule,
        ),
        title_user_template=base_preset.title_user_template,
        extra_prompt=extra_prompt.strip(),
    )


def _append_instruction(
    base: str,
    *,
    heading: str,
    text: str,
    escape_format: bool = False,
) -> str:
    stripped = text.strip()
    if not stripped:
        return base
    if escape_format:
        stripped = stripped.replace("{", "{{").replace("}", "}}")
        if "{pages_text}" in base:
            return base.replace(
                "{pages_text}",
                f"\n\n{heading}：\n{stripped}" + "{pages_text}",
                1,
            )
    return f"{base.rstrip()}\n\n{heading}：\n{stripped}"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PromptPresetError(f"Prompt preset field must be non-empty: {field_name}")


def _validate_template(
    template: str,
    *,
    field_name: str,
    allowed_fields: set[str],
    required_fields: set[str],
    sample_values: dict[str, Any],
) -> None:
    fields = _template_fields(template, field_name)
    unknown_fields = fields - allowed_fields
    if unknown_fields:
        raise PromptPresetError(
            f"Prompt preset template {field_name} uses unknown fields: "
            + ", ".join(sorted(unknown_fields))
        )

    missing_fields = required_fields - fields
    if missing_fields:
        raise PromptPresetError(
            f"Prompt preset template {field_name} is missing fields: "
            + ", ".join(sorted(missing_fields))
        )

    try:
        template.format(**sample_values)
    except (IndexError, KeyError, ValueError) as exc:
        raise PromptPresetError(
            f"Prompt preset template {field_name} is invalid: {exc}"
        ) from exc


def _template_fields(template: str, field_name: str) -> set[str]:
    try:
        parsed = Formatter().parse(template)
        fields = {
            field_name.split(".", 1)[0].split("[", 1)[0]
            for _, field_name, _, _ in parsed
            if field_name is not None and field_name
        }
    except ValueError as exc:
        raise PromptPresetError(
            f"Prompt preset template {field_name} is invalid: {exc}"
        ) from exc
    return fields
