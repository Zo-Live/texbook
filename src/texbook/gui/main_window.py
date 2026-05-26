"""Main window skeleton for the TexBook GUI."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import QMainWindow

from texbook.gui.display import GuiDisplayPreferences
from texbook.gui.i18n import tr
from texbook.gui.main_panel import ConversionMainPanel
from texbook.gui.persistence import GuiPersistentState, GuiSettingsStore
from texbook.gui.resources import APP_DISPLAY_NAME, resolve_app_icon_path
from texbook.gui.theme import build_fluent_stylesheet


class MainWindow(QMainWindow):
    """Empty application shell for later Fluent Design panels."""

    def __init__(self, *, settings_store: GuiSettingsStore | None = None) -> None:
        super().__init__()
        self._settings_store = settings_store or GuiSettingsStore()
        self._initial_state = self._settings_store.load_state()
        self._display_preferences = self._initial_state.display_preferences
        self.setWindowTitle(self._tr("app.window_title"))
        self.setMinimumSize(QSize(960, 640))
        self.resize(QSize(1180, 760))

        icon_path = resolve_app_icon_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setStyleSheet(build_fluent_stylesheet(self._display_preferences.theme))
        self._setup_menu_bar()
        self._setup_status_bar()
        panel = ConversionMainPanel(
            self,
            display_preferences=self._display_preferences,
        )
        panel.display_preferences_changed.connect(self._apply_display_preferences)
        self.setCentralWidget(panel)
        self._restore_gui_state(panel)

    def _tr(self, key: str, **kwargs: object) -> str:
        return tr(self._display_preferences.language, key, **kwargs)

    def _setup_menu_bar(self) -> None:
        self._file_menu = self.menuBar().addMenu("")
        self._exit_action = QAction(self)
        self._exit_action.triggered.connect(self.close)
        self._file_menu.addAction(self._exit_action)

        self._help_menu = self.menuBar().addMenu("")
        self._about_action = QAction(self)
        self._about_action.setEnabled(False)
        self._help_menu.addAction(self._about_action)
        self._retranslate_ui()

    def _setup_status_bar(self) -> None:
        self.statusBar().showMessage(self._tr("status.ready"))

    def _restore_gui_state(self, panel: ConversionMainPanel) -> None:
        panel.set_path_memory(self._initial_state.path_memory)
        panel.set_settings(self._initial_state.settings)

    def _apply_display_preferences(self, preferences: object) -> None:
        if not isinstance(preferences, GuiDisplayPreferences):
            return
        self._display_preferences = preferences
        self.setWindowTitle(self._tr("app.window_title"))
        self.setStyleSheet(build_fluent_stylesheet(preferences.theme))
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(self._tr("app.window_title"))
        self._file_menu.setTitle(self._tr("menu.file"))
        self._exit_action.setText(self._tr("menu.exit"))
        self._help_menu.setTitle(self._tr("menu.help"))
        self._about_action.setText(self._tr("menu.about", app_name=APP_DISPLAY_NAME))

    def _save_gui_state(self) -> None:
        panel = self.centralWidget()
        if not isinstance(panel, ConversionMainPanel):
            return
        self._settings_store.save_state(
            GuiPersistentState(
                settings=panel.current_settings(),
                path_memory=panel.current_path_memory(),
                display_preferences=panel.current_display_preferences(),
            )
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_gui_state()
        panel = self.centralWidget()
        close_executor = getattr(panel, "close_executor", None)
        if callable(close_executor):
            close_executor()
        super().closeEvent(event)
