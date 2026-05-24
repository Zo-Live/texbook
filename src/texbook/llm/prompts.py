"""Prompt construction for PDF-to-LaTeX conversion."""

from typing import Any, Dict, List, Sequence

from ..extract.base import PdfPageContext
from .presets import (
    PromptPreset,
    SYSTEM_PROMPT as SYSTEM_PROMPT,
    TITLE_SYSTEM_PROMPT as TITLE_SYSTEM_PROMPT,
    default_prompt_preset,
)


def build_chunk_messages(
    *,
    document_title: str,
    pages: Sequence[PdfPageContext],
    chunk_index: int,
    total_chunks: int,
    previous_latex_tail: str = "",
    extra_prompt: str = "",
    prompt_preset: PromptPreset | None = None,
) -> List[Dict[str, Any]]:
    """Build OpenAI-compatible chat messages for one PDF page chunk."""
    preset = prompt_preset or default_prompt_preset()
    user_content: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": _build_chunk_text(
                document_title=document_title,
                pages=pages,
                chunk_index=chunk_index,
                total_chunks=total_chunks,
                previous_latex_tail=previous_latex_tail,
                prompt_preset=preset,
            ),
        }
    ]

    for page in pages:
        if not page.image_base64:
            continue
        user_content.append(
            {
                "type": "text",
                "text": preset.page_image_label_template.format(
                    page_number=page.page_number
                ),
            }
        )
        user_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:{page.image_mime_type};base64,{page.image_base64}"
                    )
                },
            }
        )

    system_content = _with_extra_prompt(
        preset.chunk_system_prompt,
        preset_extra_prompt=preset.extra_prompt,
        runtime_extra_prompt=extra_prompt,
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def build_title_messages(
    *,
    fallback_title: str,
    title_evidence: str,
    extra_prompt: str = "",
    prompt_preset: PromptPreset | None = None,
) -> List[Dict[str, Any]]:
    """Build OpenAI-compatible chat messages for document title generation."""
    preset = prompt_preset or default_prompt_preset()
    system_content = _with_extra_prompt(
        preset.title_system_prompt,
        preset_extra_prompt=preset.extra_prompt,
        runtime_extra_prompt=extra_prompt,
    )

    user_text = preset.title_user_template.format(
        fallback_title=fallback_title,
        title_evidence=title_evidence.strip() or "[无额外线索]",
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_text},
    ]


def _build_chunk_text(
    *,
    document_title: str,
    pages: Sequence[PdfPageContext],
    chunk_index: int,
    total_chunks: int,
    previous_latex_tail: str,
    prompt_preset: PromptPreset,
) -> str:
    previous_latex_tail_section = ""
    if previous_latex_tail:
        previous_latex_tail_section = (
            "\n\n上一分块末尾 LaTeX 片段如下，只用于避免重复和衔接上下文：\n"
            f"{previous_latex_tail}"
        )

    return prompt_preset.chunk_user_template.format(
        document_title=document_title,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        previous_latex_tail_section=previous_latex_tail_section,
        pages_text=_build_pages_text(pages),
    )


def _build_pages_text(pages: Sequence[PdfPageContext]) -> str:
    lines: list[str] = []
    for page in pages:
        lines.extend(
            [
                "",
                f"--- PAGE {page.page_number} ---",
                f"页面尺寸：{page.width:.2f} x {page.height:.2f}",
                "文本块（格式：bbox | font_size | type | text）：",
            ]
        )
        if not page.text_blocks:
            lines.append("[无可用文本层]")
            continue
        for block in page.text_blocks:
            bbox = ", ".join(f"{value:.1f}" for value in block.bbox)
            lines.append(
                f"[{bbox}] | {block.font_size:.1f} | "
                f"{block.block_type} | {block.text}"
            )

    return "\n".join(lines)


def _with_extra_prompt(
    system_prompt: str,
    *,
    preset_extra_prompt: str,
    runtime_extra_prompt: str,
) -> str:
    extras = [
        value.strip()
        for value in (preset_extra_prompt, runtime_extra_prompt)
        if value.strip()
    ]
    if not extras:
        return system_prompt
    return f"{system_prompt.rstrip()}\n\n额外要求：\n" + "\n".join(extras)
