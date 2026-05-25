"""TexBook Windows GUI package."""

from texbook.gui.app import main
from texbook.gui.main_window import MainWindow
from texbook.gui.resources import (
    APP_DISPLAY_NAME,
    APP_ORGANIZATION_NAME,
    APP_WINDOW_TITLE,
    resolve_app_icon_path,
)

__all__ = [
    "APP_DISPLAY_NAME",
    "APP_ORGANIZATION_NAME",
    "APP_WINDOW_TITLE",
    "MainWindow",
    "main",
    "resolve_app_icon_path",
]
