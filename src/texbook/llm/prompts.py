"""Prompt construction for PDF-to-LaTeX conversion."""

from typing import Any, Dict, List, Sequence

from ..extract.base import PdfPageContext
from ..structure import StructureEvidence
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


STRUCTURE_SYSTEM_PROMPT = """你是中文数学教材的结构规划助手。

任务：只寻找有助于把 PDF 划分为章级 LaTeX 项目文件的结构线索，例如目录、书签、章标题、附录和页码范围。

硬性要求：
1. 只输出 JSON 对象，不要输出 Markdown 代码块。
2. JSON 格式必须为 {"status": "...", "plan": [...], "confidence": 0.0, "reason": "...", "needed_pages": [], "notes": []}。
3. status 只能是 "complete"、"need_more" 或 "insufficient"。
4. plan 中每项格式为 {"kind": "frontmatter|chapter|appendix", "title": "...", "start_page": 1, "end_page": 10, "confidence": 0.0}。
5. 页码必须使用 PDF 物理页码，不要使用教材印刷页码。
6. 只做结构判断，不要转写正文、公式或证明细节。
7. 如果当前输入足以确定章级结构，输出 status="complete"。
8. 如果当前输入看起来是目录或结构页但还缺少后续页，输出 status="need_more"，并说明需要继续读取哪些后续 PDF 页。
9. 如果当前输入不足以从目录规划结构，输出 status="insufficient"，并保留能确定的线索。
"""


def build_structure_messages(
    *,
    document_title: str,
    evidence: StructureEvidence,
    pages: Sequence[PdfPageContext] = (),
    inspected_pages: Sequence[int] = (),
    stage: str = "toc",
    extra_prompt: str = "",
) -> List[Dict[str, Any]]:
    """Build OpenAI-compatible messages for structure planning."""
    text = _build_structure_text(
        document_title=document_title,
        evidence=evidence,
        pages=pages,
        inspected_pages=inspected_pages,
        stage=stage,
    )
    user_content: List[Dict[str, Any]] = [{"type": "text", "text": text}]

    for page in pages:
        if not page.image_base64:
            continue
        user_content.append(
            {
                "type": "text",
                "text": f"下面是第 {page.page_number} 页的页面图像，只用于判断目录和章级结构：",
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

    return [
        {
            "role": "system",
            "content": _with_extra_prompt(
                STRUCTURE_SYSTEM_PROMPT,
                preset_extra_prompt="",
                runtime_extra_prompt=extra_prompt,
            ),
        },
        {"role": "user", "content": user_content},
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


def _build_structure_text(
    *,
    document_title: str,
    evidence: StructureEvidence,
    pages: Sequence[PdfPageContext],
    inspected_pages: Sequence[int],
    stage: str,
) -> str:
    if stage == "headings":
        instruction = (
            "当前没有可靠目录。请根据全书标题候选、字号、书签残余线索和页面开头文本，"
            "推断章级结构。只输出最可信的顶层章节、前置内容和附录范围。"
        )
    else:
        instruction = (
            "请判断已提供的开头页面是否包含足够目录信息。"
            "如果足够，输出完整章级结构；如果目录跨页且还没读完，返回 need_more；"
            "如果这些开头页面不是可用目录，返回 insufficient。"
        )

    lines = [
        f"文档标题：{document_title}",
        f"规划阶段：{stage}",
        f"已经检查的 PDF 页：{', '.join(str(page) for page in inspected_pages) or '[无]'}",
        "",
        instruction,
        "",
        evidence.format_for_llm(),
    ]

    if pages:
        lines.extend(["", "当前发送页面的文本块：", _build_pages_text(pages)])

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
