"""Tests for prompt preset loading and validation."""

import json

import pytest

from latex_tools.llm.presets import (
    DEFAULT_PROMPT_PRESET_NAME,
    PromptPreset,
    PromptPresetError,
    build_prompt_preset_from_inputs,
    default_prompt_preset,
    list_prompt_presets,
    load_prompt_preset,
    save_prompt_preset,
    validate_prompt_preset_name,
)


def _preset(name="custom-one", *, extra_prompt=""):
    base = default_prompt_preset()
    return PromptPreset(
        name=name,
        description="Custom preset",
        version="1",
        chunk_system_prompt=base.chunk_system_prompt + "\n自定义正文规则",
        chunk_user_template=base.chunk_user_template,
        page_image_label_template=base.page_image_label_template,
        title_system_prompt=base.title_system_prompt + "\n自定义标题规则",
        title_user_template=base.title_user_template,
        extra_prompt=extra_prompt,
    )


def test_loads_builtin_default_prompt_preset():
    preset = load_prompt_preset(DEFAULT_PROMPT_PRESET_NAME, repo_root=object())

    assert preset.name == DEFAULT_PROMPT_PRESET_NAME
    assert "中文数学讲义" in preset.description
    assert "{pages_text}" in preset.chunk_user_template


def test_saves_loads_and_lists_repository_prompt_preset(tmp_path):
    preset = _preset(extra_prompt="默认额外说明")

    path = save_prompt_preset(preset, repo_root=tmp_path)
    loaded = load_prompt_preset("custom-one", repo_root=tmp_path)
    listed = list_prompt_presets(repo_root=tmp_path)

    assert path == tmp_path / "config/latex_tools/presets/custom-one.json"
    assert loaded == preset
    assert [item.preset.name for item in listed] == [
        DEFAULT_PROMPT_PRESET_NAME,
        "custom-one",
    ]
    assert listed[1].source == "repo"


def test_repository_prompt_preset_requires_overwrite(tmp_path):
    preset = _preset()
    replacement = _preset(extra_prompt="替换")

    save_prompt_preset(preset, repo_root=tmp_path)

    with pytest.raises(PromptPresetError, match="already exists"):
        save_prompt_preset(replacement, repo_root=tmp_path)

    save_prompt_preset(replacement, repo_root=tmp_path, overwrite=True)

    assert load_prompt_preset("custom-one", repo_root=tmp_path).extra_prompt == "替换"


def test_rejects_invalid_names_and_builtin_overwrite(tmp_path):
    with pytest.raises(PromptPresetError):
        validate_prompt_preset_name("中文")

    with pytest.raises(PromptPresetError, match="Cannot overwrite built-in"):
        save_prompt_preset(default_prompt_preset(), repo_root=tmp_path)

    with pytest.raises(PromptPresetError, match="Unknown prompt preset"):
        load_prompt_preset("missing-one", repo_root=tmp_path)


def test_repository_prompt_preset_file_name_must_match_name(tmp_path):
    preset = _preset()
    path = tmp_path / "config/latex_tools/presets/wrong-name.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(preset.to_dict(), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(PromptPresetError, match="file name"):
        load_prompt_preset("wrong-name", repo_root=tmp_path)

    with pytest.raises(PromptPresetError, match="file name"):
        list_prompt_presets(repo_root=tmp_path)


def test_build_prompt_preset_from_friendly_inputs_escapes_template_braces():
    preset = build_prompt_preset_from_inputs(
        name="friendly-one",
        description="友好输入预设",
        base_preset=default_prompt_preset(),
        chunk_rule="只保留定理和证明",
        chunk_context="保留原文中的 {特殊标记}",
        title_rule="标题保留章节编号",
        extra_prompt="不要生成习题答案",
    )

    assert "只保留定理和证明" in preset.chunk_system_prompt
    assert "保留原文中的 {{特殊标记}}" in preset.chunk_user_template
    assert "标题保留章节编号" in preset.title_system_prompt
    assert preset.extra_prompt == "不要生成习题答案"
