"""Tests for LLM response parsing and prompt generation."""

import sys
from types import SimpleNamespace

from texbook.extract.base import PageTextBlock, PdfPageContext
from texbook.llm.client import (
    LLMResponseError,
    OpenAICompatibleClient,
    parse_chunk_response,
    parse_title_response,
)
from texbook.llm.config import LLMConfig
from texbook.llm.prompts import build_chunk_messages, build_title_messages
from texbook.llm.presets import PromptPreset, default_prompt_preset


def test_parse_chunk_response_accepts_fenced_json():
    result = parse_chunk_response(
        """```json
        {"latex": "\\section{集合}", "notes": ["ignored footer removed"]}
        ```"""
    )

    assert result.latex == "\\section{集合}"
    assert result.notes == ["ignored footer removed"]


def test_parse_chunk_response_rejects_missing_latex():
    try:
        parse_chunk_response('{"notes": []}')
    except LLMResponseError as exc:
        assert "latex" in str(exc)
    else:
        raise AssertionError("Expected LLMResponseError")


def test_parse_title_response_normalizes_title():
    title = parse_title_response('{"title": "  6.1\\n集合与映射  "}')

    assert title == "6.1 集合与映射"


def test_parse_title_response_rejects_missing_title():
    try:
        parse_title_response('{"latex": "\\\\section{集合}"}')
    except LLMResponseError as exc:
        assert "title" in str(exc)
    else:
        raise AssertionError("Expected LLMResponseError")


def test_openai_client_uses_unlimited_read_timeout_by_default(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    OpenAICompatibleClient(
        LLMConfig(
            model="test-model",
            api_key="test-key",
        )
    )

    assert captured["timeout"].read is None


def test_openai_client_uses_explicit_read_timeout(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    OpenAICompatibleClient(
        LLMConfig(
            model="test-model",
            api_key="test-key",
            timeout=10.0,
        )
    )

    assert captured["timeout"].read == 10.0


def test_build_chunk_messages_contains_page_text_and_image():
    page = PdfPageContext(
        page_number=2,
        width=640,
        height=360,
        text_blocks=[
            PageTextBlock(
                text="集合的定义",
                bbox=(10, 20, 200, 40),
                font_size=18,
                block_type="heading",
            )
        ],
        image_base64="ZmFrZQ==",
    )

    messages = build_chunk_messages(
        document_title="第六章",
        pages=[page],
        chunk_index=1,
        total_chunks=1,
        previous_latex_tail="\\section{引言}",
    )

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    content = messages[1]["content"]
    assert any(item["type"] == "text" and "第六章" in item["text"] for item in content)
    assert any(item["type"] == "text" and "PAGE 2" in item["text"] for item in content)
    assert any(item["type"] == "image_url" for item in content)


def test_build_chunk_messages_contains_complex_content_policy():
    messages = build_chunk_messages(
        document_title="第六章",
        pages=[PdfPageContext(page_number=1, width=1, height=1)],
        chunk_index=1,
        total_chunks=1,
    )

    system = messages[0]["content"]
    assert "tabular" in system
    assert "% TODO: table" in system
    assert "% TODO: figure pending_asset" in system
    assert r"\includegraphics" in system
    assert "% TODO: layout" in system


def test_build_title_messages_contains_fallback_and_evidence():
    messages = build_title_messages(
        fallback_title="6.1 集合与映射",
        title_evidence="\\section{集合}",
        extra_prompt="保持章节编号",
    )

    assert messages[0]["role"] == "system"
    assert "保持章节编号" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "6.1 集合与映射" in messages[1]["content"]
    assert "\\section{集合}" in messages[1]["content"]


def test_build_messages_use_custom_prompt_preset():
    base = default_prompt_preset()
    preset = PromptPreset(
        name="custom-client",
        description="Custom prompt",
        version="1",
        chunk_system_prompt="正文系统",
        chunk_user_template="正文用户 {document_title}{pages_text}",
        page_image_label_template="图像页 {page_number}",
        title_system_prompt="标题系统",
        title_user_template="标题用户 {fallback_title}\n{title_evidence}",
        extra_prompt="预设额外",
    )
    page = PdfPageContext(
        page_number=3,
        width=1,
        height=1,
        text_blocks=[
            PageTextBlock(
                text="页面文本",
                bbox=(0, 0, 1, 1),
                font_size=12,
            )
        ],
        image_base64="ZmFrZQ==",
    )

    chunk_messages = build_chunk_messages(
        document_title="自定义标题",
        pages=[page],
        chunk_index=1,
        total_chunks=1,
        extra_prompt="运行额外",
        prompt_preset=preset,
    )
    title_messages = build_title_messages(
        fallback_title="文件名",
        title_evidence="标题线索",
        prompt_preset=preset,
    )

    assert base.name == "chinese-math"
    assert "正文系统" in chunk_messages[0]["content"]
    assert "预设额外" in chunk_messages[0]["content"]
    assert "运行额外" in chunk_messages[0]["content"]
    assert "正文用户 自定义标题" in chunk_messages[1]["content"][0]["text"]
    assert "图像页 3" == chunk_messages[1]["content"][1]["text"]
    assert title_messages[0]["content"].startswith("标题系统")
    assert title_messages[1]["content"] == "标题用户 文件名\n标题线索"
