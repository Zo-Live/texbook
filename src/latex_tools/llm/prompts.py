"""Prompt construction for PDF-to-LaTeX conversion."""

from typing import Any, Dict, List, Sequence

from ..extract.base import PdfPageContext


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


def build_chunk_messages(
    *,
    document_title: str,
    pages: Sequence[PdfPageContext],
    chunk_index: int,
    total_chunks: int,
    previous_latex_tail: str = "",
    extra_prompt: str = "",
) -> List[Dict[str, Any]]:
    """Build OpenAI-compatible chat messages for one PDF page chunk."""
    user_content: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": _build_chunk_text(
                document_title=document_title,
                pages=pages,
                chunk_index=chunk_index,
                total_chunks=total_chunks,
                previous_latex_tail=previous_latex_tail,
            ),
        }
    ]

    for page in pages:
        if not page.image_base64:
            continue
        user_content.append(
            {
                "type": "text",
                "text": f"下面是第 {page.page_number} 页的页面图像：",
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

    system_content = SYSTEM_PROMPT
    if extra_prompt:
        system_content += f"\n\n额外要求：{extra_prompt}"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def _build_chunk_text(
    *,
    document_title: str,
    pages: Sequence[PdfPageContext],
    chunk_index: int,
    total_chunks: int,
    previous_latex_tail: str,
) -> str:
    lines = [
        f"文档标题：{document_title}",
        f"当前分块：{chunk_index}/{total_chunks}",
        "",
        "请把本分块页面整理成连续的 LaTeX 正文片段。",
        "辅助文本识别可能有断行、漏公式、符号误识别；页面图像优先级更高。",
    ]

    if previous_latex_tail:
        lines.extend(
            [
                "",
                "上一分块末尾 LaTeX 片段如下，只用于避免重复和衔接上下文：",
                previous_latex_tail,
            ]
        )

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
