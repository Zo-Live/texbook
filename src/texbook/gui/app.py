"""Qt application bootstrap for the TexBook GUI."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from texbook.gui.main_window import MainWindow
from texbook.gui.resources import (
    APP_DISPLAY_NAME,
    APP_ORGANIZATION_NAME,
    resolve_app_icon_path,
)

GUI_FONT_FAMILIES = ("Microsoft YaHei UI", "Segoe UI", "Arial")
GUI_BASE_FONT_POINT_SIZE = 11


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Create or reuse the Qt application object."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv is not None else sys.argv)

    app.setApplicationName(APP_DISPLAY_NAME)
    app.setOrganizationName(APP_ORGANIZATION_NAME)
    app.setFont(_build_application_font(app.font()))

    icon_path = resolve_app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    return app


def _build_application_font(current_font: QFont) -> QFont:
    font = QFont(current_font)
    font.setFamilies(list(GUI_FONT_FAMILIES))
    font.setPointSize(GUI_BASE_FONT_POINT_SIZE)
    return font


def main(argv: Sequence[str] | None = None) -> int:
    """Run the GUI application."""
    app = create_application(argv)
    window = MainWindow()
    window.show()
    return app.exec()
