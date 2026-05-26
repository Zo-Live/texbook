"""GUI display preferences for theme, language, and size."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QFont

DEFAULT_GUI_FONT_FAMILY = "Microsoft YaHei UI"
GUI_FONT_FALLBACKS = (DEFAULT_GUI_FONT_FAMILY, "Segoe UI", "Arial")
DEFAULT_GUI_FONT_POINT_SIZE = 11
MIN_GUI_FONT_POINT_SIZE = 8
MAX_GUI_FONT_POINT_SIZE = 24


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
    font_point_size: int = DEFAULT_GUI_FONT_POINT_SIZE

    def __post_init__(self) -> None:
        theme = self.theme
        if isinstance(theme, str):
            theme = GuiThemeMode(theme)
        language = self.language
        if isinstance(language, str):
            language = GuiLanguage(language)
        object.__setattr__(self, "theme", theme)
        object.__setattr__(self, "language", language)
        object.__setattr__(
            self,
            "font_point_size",
            coerce_font_point_size(self.font_point_size),
        )


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


def coerce_font_point_size(
    value: object,
    default: int = DEFAULT_GUI_FONT_POINT_SIZE,
) -> int:
    """Return a bounded GUI font point size."""
    try:
        point_size = int(value)
    except (TypeError, ValueError):
        return default
    return max(MIN_GUI_FONT_POINT_SIZE, min(MAX_GUI_FONT_POINT_SIZE, point_size))


def build_gui_font(
    font_point_size: int,
    *,
    current_font: QFont | None = None,
) -> QFont:
    """Build a Qt font that applies the configured GUI display preferences."""
    font = QFont(current_font or QFont())
    font.setFamilies([DEFAULT_GUI_FONT_FAMILY, *GUI_FONT_FALLBACKS])
    font.setPointSize(coerce_font_point_size(font_point_size))
    return font
