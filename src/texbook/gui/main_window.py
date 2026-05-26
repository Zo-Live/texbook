"""Main window skeleton for the TexBook GUI."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import QMainWindow

from texbook.gui.main_panel import ConversionMainPanel
from texbook.gui.persistence import GuiPersistentState, GuiSettingsStore
from texbook.gui.resources import APP_DISPLAY_NAME, APP_WINDOW_TITLE, resolve_app_icon_path
from texbook.gui.theme import build_fluent_stylesheet


class MainWindow(QMainWindow):
    """Empty application shell for later Fluent Design panels."""

    def __init__(self, *, settings_store: GuiSettingsStore | None = None) -> None:
        super().__init__()
        self._settings_store = settings_store or GuiSettingsStore()
        self.setWindowTitle(APP_WINDOW_TITLE)
        self.setMinimumSize(QSize(960, 640))
        self.resize(QSize(1180, 760))

        icon_path = resolve_app_icon_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setStyleSheet(build_fluent_stylesheet())
        self._setup_menu_bar()
        self._setup_status_bar()
        panel = ConversionMainPanel(self)
        self.setCentralWidget(panel)
        self._restore_gui_state(panel)

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

    def _restore_gui_state(self, panel: ConversionMainPanel) -> None:
        state = self._settings_store.load_state()
        panel.set_path_memory(state.path_memory)
        panel.set_settings(state.settings)

    def _save_gui_state(self) -> None:
        panel = self.centralWidget()
        if not isinstance(panel, ConversionMainPanel):
            return
        self._settings_store.save_state(
            GuiPersistentState(
                settings=panel.current_settings(),
                path_memory=panel.current_path_memory(),
            )
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_gui_state()
        panel = self.centralWidget()
        close_executor = getattr(panel, "close_executor", None)
        if callable(close_executor):
            close_executor()
        super().closeEvent(event)
