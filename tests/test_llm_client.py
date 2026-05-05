"""Tests for LLM response parsing and prompt generation."""

import sys
from types import SimpleNamespace

from latex_tools.extract.base import PageTextBlock, PdfPageContext
from latex_tools.llm.client import (
    LLMResponseError,
    OpenAICompatibleClient,
    parse_chunk_response,
)
from latex_tools.llm.config import LLMConfig
from latex_tools.llm.prompts import build_chunk_messages


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
