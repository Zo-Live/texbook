"""Main window skeleton for the TexBook GUI."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMainWindow

from texbook.gui.main_panel import ConversionMainPanel
from texbook.gui.resources import APP_DISPLAY_NAME, APP_WINDOW_TITLE, resolve_app_icon_path
from texbook.gui.theme import build_fluent_stylesheet


class MainWindow(QMainWindow):
    """Empty application shell for later Fluent Design panels."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_WINDOW_TITLE)
        self.setMinimumSize(QSize(960, 640))
        self.resize(QSize(1180, 760))

        icon_path = resolve_app_icon_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setStyleSheet(build_fluent_stylesheet())
        self._setup_menu_bar()
        self._setup_status_bar()
        self.setCentralWidget(ConversionMainPanel(self))

    def _setup_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = self.menuBar().addMenu("帮助")
        about_action = QAction(f"关于 {APP_DISPLAY_NAME}", self)
        about_action.setEnabled(False)
        help_menu.addAction(about_action)

    def _setup_status_bar(self) -> None:
        self.statusBar().showMessage("就绪")
