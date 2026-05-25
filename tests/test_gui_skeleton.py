"""Tests for the GUI application skeleton."""

from __future__ import annotations

import os
from pathlib import Path
import runpy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget  # noqa: E402

from texbook.gui.app import create_application  # noqa: E402
from texbook.gui.main_panel import ConversionMainPanel  # noqa: E402
from texbook.gui.main_window import MainWindow  # noqa: E402
from texbook.gui.resources import (  # noqa: E402
    APP_DISPLAY_NAME,
    APP_ORGANIZATION_NAME,
    APP_WINDOW_TITLE,
    resolve_app_icon_path,
)


ROOT = Path(__file__).resolve().parents[1]


def test_icon_resource_resolves_to_docs_icon():
    assert resolve_app_icon_path() == ROOT / "docs" / "icon.ico"


def test_gui_import_does_not_create_qapplication():
    before = QApplication.instance()
    script_globals = runpy.run_path(str(ROOT / "src" / "texbook" / "gui" / "app.py"))

    assert "main" in script_globals
    assert QApplication.instance() is before


def test_create_application_sets_metadata():
    app = create_application(["texbook-gui-test"])

    assert app.applicationName() == APP_DISPLAY_NAME
    assert app.organizationName() == APP_ORGANIZATION_NAME
    assert not app.windowIcon().isNull()

    app.quit()


def test_main_window_has_basic_lifecycle_shell():
    app = create_application(["texbook-gui-test"])
    window = MainWindow()

    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == APP_WINDOW_TITLE
    assert not window.windowIcon().isNull()
    assert isinstance(window.centralWidget(), ConversionMainPanel)
    assert window.menuBar().actions()
    assert window.statusBar().currentMessage() == "就绪"

    window.close()
    app.quit()


def test_pyinstaller_spec_references_gui_entry_and_icon():
    spec_text = (ROOT / "packaging" / "texbook-gui.spec").read_text(encoding="utf-8")

    assert "ROOT = Path(SPECPATH).parent" in spec_text
    assert "src\" / \"texbook\" / \"gui\" / \"__main__.py" in spec_text
    assert "docs\" / \"icon.ico" in spec_text
    assert "datas=[(str(ICON_PATH), \"docs\")]" in spec_text
    assert "icon=str(ICON_PATH)" in spec_text
    assert "console=False" in spec_text


def test_main_window_shows_conversion_tool_panel_immediately():
    app = create_application(["texbook-gui-test"])
    window = MainWindow()
    central = window.centralWidget()

    assert isinstance(central, ConversionMainPanel)
    assert central.objectName() == "conversionMainPanel"
    assert central.findChild(QWidget, "inputPanel") is not None
    assert central.findChild(QWidget, "outputPanel") is not None
    assert central.findChild(QWidget, "modePanel") is not None
    assert central.findChild(QWidget, "parametersPanel") is not None
    assert central.findChild(QWidget, "taskListPanel") is not None
    assert central.findChild(QWidget, "startButton") is not None
    assert central.findChild(QWidget, "addTaskButton") is not None
    assert central.findChild(QWidget, "emptyCentralWidget") is None

    window.close()
    app.quit()


def test_conversion_panel_exposes_future_task_control_points():
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()

    for object_name in [
        "pdfInputField",
        "pdfInputBrowseButton",
        "outputDirectoryField",
        "outputBrowseButton",
        "singleFileModeRadio",
        "projectModeRadio",
        "batchModeRadio",
        "pagesField",
        "documentClassCombo",
        "structureModeCombo",
        "modelField",
        "baseUrlField",
        "apiKeyField",
        "promptPresetCombo",
        "extraPromptEdit",
        "cacheEnabledCheckBox",
        "cacheDirectoryField",
        "chunkPagesSpinBox",
        "prefetchChunksSpinBox",
        "llmConcurrencySpinBox",
        "batchWorkersSpinBox",
        "advancedOptionsPanel",
        "overallProgressBar",
        "taskEmptyStatusLabel",
    ]:
        assert panel.findChild(QWidget, object_name) is not None

    panel.close()
    app.quit()
