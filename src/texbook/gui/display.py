"""GUI display preferences for theme and language."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GuiThemeMode(str, Enum):
    """Theme modes exposed by the GUI."""

    light = "light"
    dark = "dark"


class GuiLanguage(str, Enum):
    """Interface languages exposed by the GUI."""

    zh_CN = "zh_CN"
    en_US = "en_US"


@dataclass(frozen=True)
class GuiDisplayPreferences:
    """Persistent GUI display preferences."""

    theme: GuiThemeMode = GuiThemeMode.light
    language: GuiLanguage = GuiLanguage.zh_CN

    def __post_init__(self) -> None:
        theme = self.theme
        if isinstance(theme, str):
            theme = GuiThemeMode(theme)
        language = self.language
        if isinstance(language, str):
            language = GuiLanguage(language)
        object.__setattr__(self, "theme", theme)
        object.__setattr__(self, "language", language)


def coerce_theme_mode(value: object, default: GuiThemeMode = GuiThemeMode.light) -> GuiThemeMode:
    """Return a valid theme mode from a persisted value."""
    try:
        return GuiThemeMode(str(value))
    except (TypeError, ValueError):
        return default


def coerce_language(value: object, default: GuiLanguage = GuiLanguage.zh_CN) -> GuiLanguage:
    """Return a valid language from a persisted value."""
    try:
        return GuiLanguage(str(value))
    except (TypeError, ValueError):
        return default
