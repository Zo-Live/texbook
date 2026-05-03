"""Tests for CLI helper behavior."""

import pytest
import typer

from latex_tools.cli import _build_converter, _parse_pages


class DummyClient:
    def generate_latex_chunk(self, **kwargs):
        raise AssertionError("Not used in converter construction test")


def test_parse_pages_accepts_ranges_and_deduplicates():
    assert _parse_pages("1,3-5,3") == [1, 3, 4, 5]


def test_parse_pages_all_when_empty():
    assert _parse_pages(None) is None
    assert _parse_pages(" ") is None


def test_parse_pages_rejects_invalid_range():
    with pytest.raises(typer.BadParameter):
        _parse_pages("5-3")


def test_build_converter_normalizes_image_options():
    converter = _build_converter(
        model="test-model",
        api_key="test-key",
        base_url=None,
        temperature=1.0,
        timeout=10.0,
        max_tokens=128,
        chunk_pages=2,
        image_dpi=144,
        image_dpi_min=90,
        image_dpi_max=None,
        image_format="jpg",
        jpeg_quality=92,
        client=DummyClient(),
    )

    assert converter.image_options.dpi == 144
    assert converter.image_options.dpi_min == 90
    assert converter.image_options.dpi_max == 144
    assert converter.image_options.image_format == "jpeg"
    assert converter.image_options.jpeg_quality == 92


def test_build_converter_rejects_invalid_image_settings():
    with pytest.raises(typer.BadParameter):
        _build_converter(
            model="test-model",
            api_key="test-key",
            base_url=None,
            temperature=1.0,
            timeout=10.0,
            max_tokens=128,
            chunk_pages=2,
            image_dpi=144,
            image_format="gif",
            client=DummyClient(),
        )

    with pytest.raises(typer.BadParameter):
        _build_converter(
            model="test-model",
            api_key="test-key",
            base_url=None,
            temperature=1.0,
            timeout=10.0,
            max_tokens=128,
            chunk_pages=2,
            image_dpi=144,
            image_dpi_min=200,
            image_dpi_max=100,
            client=DummyClient(),
        )

    with pytest.raises(typer.BadParameter):
        _build_converter(
            model="test-model",
            api_key="test-key",
            base_url=None,
            temperature=1.0,
            timeout=10.0,
            max_tokens=128,
            chunk_pages=2,
            image_dpi=144,
            jpeg_quality=0,
            client=DummyClient(),
        )
