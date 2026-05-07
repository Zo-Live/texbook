"""Tests for CLI helper behavior."""

import pytest
import typer
from typer.testing import CliRunner

from latex_tools import cli as cli_module
from latex_tools.cli import TitleSource, _build_converter, _parse_pages, app
from latex_tools.llm.presets import PromptPreset, default_prompt_preset


class DummyClient:
    def generate_latex_chunk(self, **kwargs):
        raise AssertionError("Not used in converter construction test")


runner = CliRunner()


def _custom_preset():
    base = default_prompt_preset()
    return PromptPreset(
        name="custom-cli",
        description="Custom CLI preset",
        version="1",
        chunk_system_prompt=base.chunk_system_prompt,
        chunk_user_template=base.chunk_user_template,
        page_image_label_template=base.page_image_label_template,
        title_system_prompt=base.title_system_prompt,
        title_user_template=base.title_user_template,
        extra_prompt="CLI preset extra",
    )


def test_parse_pages_accepts_ranges_and_deduplicates():
    assert _parse_pages("1,3-5,3") == [1, 3, 4, 5]


def test_parse_pages_all_when_empty():
    assert _parse_pages(None) is None
    assert _parse_pages(" ") is None


def test_parse_pages_rejects_invalid_range():
    with pytest.raises(typer.BadParameter):
        _parse_pages("5-3")


def test_build_converter_normalizes_image_options(tmp_path):
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
        prefetch_chunks=2,
        cache_dir=tmp_path / "cache",
        client=DummyClient(),
    )

    assert converter.image_options.dpi == 144
    assert converter.image_options.dpi_min == 90
    assert converter.image_options.dpi_max == 144
    assert converter.image_options.image_format == "jpeg"
    assert converter.image_options.jpeg_quality == 92
    assert converter.prefetch_chunks == 2
    assert converter.cache_options is not None
    assert converter.cache_options.cache_dir == tmp_path / "cache"
    assert converter.cache_options.llm_model == "test-model"
    assert converter.cache_options.clear is False
    assert converter.prompt_preset.name == "chinese-math"
    assert converter.title_source == "filename"
    assert converter.manual_title is None
    assert converter.show_date is False


def test_build_converter_passes_title_and_date_options(tmp_path):
    converter = _build_converter(
        model="test-model",
        api_key="test-key",
        base_url=None,
        temperature=1.0,
        timeout=10.0,
        max_tokens=128,
        chunk_pages=2,
        image_dpi=144,
        cache_dir=tmp_path / "cache",
        title_source=TitleSource.filename,
        manual_title=" 手动标题 ",
        show_date=True,
        client=DummyClient(),
    )

    assert converter.title_source == "filename"
    assert converter.manual_title == "手动标题"
    assert converter.show_date is True

    llm_converter = _build_converter(
        model="test-model",
        api_key="test-key",
        base_url=None,
        temperature=1.0,
        timeout=10.0,
        max_tokens=128,
        chunk_pages=2,
        image_dpi=144,
        cache_dir=tmp_path / "cache",
        title_source=TitleSource.llm,
        client=DummyClient(),
    )

    assert llm_converter.title_source == "llm"


def test_build_converter_accepts_prompt_preset_object(tmp_path):
    preset = _custom_preset()
    converter = _build_converter(
        model="test-model",
        api_key="test-key",
        base_url=None,
        temperature=1.0,
        timeout=10.0,
        max_tokens=128,
        chunk_pages=2,
        image_dpi=144,
        cache_dir=tmp_path / "cache",
        prompt_preset=preset,
        client=DummyClient(),
    )

    assert converter.prompt_preset is preset


def test_build_converter_rejects_unknown_prompt_preset(tmp_path):
    with pytest.raises(typer.BadParameter, match="Unknown prompt preset"):
        _build_converter(
            model="test-model",
            api_key="test-key",
            base_url=None,
            temperature=1.0,
            timeout=10.0,
            max_tokens=128,
            chunk_pages=2,
            image_dpi=144,
            cache_dir=tmp_path / "cache",
            preset="missing-one",
            client=DummyClient(),
        )


def test_build_converter_rejects_invalid_title_options(tmp_path):
    with pytest.raises(typer.BadParameter, match="title"):
        _build_converter(
            model="test-model",
            api_key="test-key",
            base_url=None,
            temperature=1.0,
            timeout=10.0,
            max_tokens=128,
            chunk_pages=2,
            image_dpi=144,
            cache_dir=tmp_path / "cache",
            manual_title=" ",
            client=DummyClient(),
        )

    with pytest.raises(typer.BadParameter, match="title-source"):
        _build_converter(
            model="test-model",
            api_key="test-key",
            base_url=None,
            temperature=1.0,
            timeout=10.0,
            max_tokens=128,
            chunk_pages=2,
            image_dpi=144,
            cache_dir=tmp_path / "cache",
            title_source=TitleSource.llm,
            manual_title="手动标题",
            client=DummyClient(),
        )


def test_build_converter_accepts_unlimited_timeout(tmp_path):
    converter = _build_converter(
        model="test-model",
        api_key="test-key",
        base_url=None,
        temperature=1.0,
        timeout=None,
        max_tokens=128,
        chunk_pages=2,
        image_dpi=144,
        cache_dir=tmp_path / "cache",
        client=DummyClient(),
    )

    assert converter.chunk_pages == 2


def test_build_converter_supports_cache_controls(tmp_path):
    disabled = _build_converter(
        model="test-model",
        api_key="test-key",
        base_url=None,
        temperature=1.0,
        timeout=10.0,
        max_tokens=128,
        chunk_pages=2,
        image_dpi=144,
        cache_dir=tmp_path / "cache",
        no_cache=True,
        client=DummyClient(),
    )

    assert disabled.cache_options is None

    clearing = _build_converter(
        model="test-model",
        api_key="test-key",
        base_url=None,
        temperature=1.0,
        timeout=10.0,
        max_tokens=128,
        chunk_pages=2,
        image_dpi=144,
        cache_dir=tmp_path / "cache",
        clear_cache=True,
        client=DummyClient(),
    )

    assert clearing.cache_options is not None
    assert clearing.cache_options.clear is True

    with pytest.raises(typer.BadParameter, match="clear-cache"):
        _build_converter(
            model="test-model",
            api_key="test-key",
            base_url=None,
            temperature=1.0,
            timeout=10.0,
            max_tokens=128,
            chunk_pages=2,
            image_dpi=144,
            cache_dir=tmp_path / "cache",
            no_cache=True,
            clear_cache=True,
            client=DummyClient(),
        )


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
            prefetch_chunks=-1,
            client=DummyClient(),
        )


def test_build_converter_rejects_non_positive_timeout():
    with pytest.raises(typer.BadParameter, match="Timeout"):
        _build_converter(
            model="test-model",
            api_key="test-key",
            base_url=None,
            temperature=1.0,
            timeout=0,
            max_tokens=128,
            chunk_pages=2,
            image_dpi=144,
            client=DummyClient(),
        )


def test_presets_cli_lists_builtin_preset():
    result = runner.invoke(app, ["presets", "list"])

    assert result.exit_code == 0
    assert "chinese-math" in result.output
    assert "builtin" in result.output


def test_presets_cli_adds_and_shows_repository_preset(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "_repo_root", lambda: tmp_path)

    result = runner.invoke(
        app,
        ["presets", "add", "--name", "custom-one"],
        input="\n只保留证明\n\n标题短一些\n默认额外\n",
    )
    show_result = runner.invoke(app, ["presets", "show", "custom-one"])

    assert result.exit_code == 0, result.output
    assert show_result.exit_code == 0, show_result.output
    assert "custom-one.json" in result.output
    assert '"name": "custom-one"' in show_result.output
    assert "只保留证明" in show_result.output
    assert "标题短一些" in show_result.output
    assert "默认额外" in show_result.output
