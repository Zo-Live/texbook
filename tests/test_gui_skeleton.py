"""Tests for the GUI application skeleton."""

from __future__ import annotations

import os
from pathlib import Path
import runpy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QToolButton,
    QWidget,
)

from texbook.gui.app import create_application  # noqa: E402
from texbook.gui.main_panel import ConversionMainPanel  # noqa: E402
from texbook.gui.main_window import MainWindow  # noqa: E402
from texbook.gui.resources import (  # noqa: E402
    APP_DISPLAY_NAME,
    APP_ORGANIZATION_NAME,
    APP_WINDOW_TITLE,
    resolve_app_icon_path,
)
from texbook.gui.selection import GuiInputKind, GuiInputSelection  # noqa: E402


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
    assert window.statusBar().currentMessage() == "请选择 PDF 输入和产物目录"

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


def test_gui_input_selection_accepts_windows_paths_and_filters_non_pdf():
    selection = GuiInputSelection.from_multiple_files(
        [
            r"C:\docs\a.pdf",
            r"C:\docs\ignore.txt",
            r"C:\docs\a.pdf",
            r"\\server\share\b.PDF",
        ]
    )

    assert selection.kind == GuiInputKind.multiple_files
    assert selection.paths == (r"C:\docs\a.pdf", r"\\server\share\b.PDF")
    assert selection.display_text() == r"C:\docs\a.pdf 等 2 个文件"


def test_conversion_panel_single_pdf_and_output_directory_enable_add_task(monkeypatch):
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()

    monkeypatch.setattr(
        "texbook.gui.main_panel.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (r"C:\books\lecture.pdf", "PDF 文件 (*.pdf)"),
    )
    monkeypatch.setattr(
        "texbook.gui.main_panel.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: r"D:\tex-output",
    )

    panel.findChild(QToolButton, "pdfInputBrowseButton").click()

    assert panel.selection_state.input_selection.kind == GuiInputKind.single_file
    assert panel.selection_state.input_selection.paths == (r"C:\books\lecture.pdf",)
    assert panel.findChild(QLineEdit, "pdfInputField").text() == r"C:\books\lecture.pdf"
    assert not panel.findChild(QPushButton, "addTaskButton").isEnabled()

    panel.findChild(QToolButton, "outputBrowseButton").click()

    assert panel.selection_state.output_directory == r"D:\tex-output"
    assert panel.findChild(QLineEdit, "outputDirectoryField").text() == r"D:\tex-output"
    assert panel.findChild(QPushButton, "addTaskButton").isEnabled()
    assert not panel.findChild(QPushButton, "startButton").isEnabled()

    panel.close()
    app.quit()


def test_conversion_panel_multiple_pdf_selection_is_filtered_deduped_and_summarized(
    monkeypatch,
):
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()
    panel.findChild(QComboBox, "inputTypeCombo").setCurrentText("多个 PDF")

    monkeypatch.setattr(
        "texbook.gui.main_panel.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: (
            [
                r"C:\docs\a.pdf",
                r"C:\docs\ignore.txt",
                r"C:\docs\a.pdf",
                r"\\server\share\b.PDF",
            ],
            "PDF 文件 (*.pdf)",
        ),
    )

    panel.findChild(QToolButton, "pdfInputBrowseButton").click()

    assert panel.selection_state.input_selection.kind == GuiInputKind.multiple_files
    assert panel.selection_state.input_selection.paths == (
        r"C:\docs\a.pdf",
        r"\\server\share\b.PDF",
    )
    assert panel.findChild(QLineEdit, "pdfInputField").text() == r"C:\docs\a.pdf 等 2 个文件"
    assert not panel.findChild(QPushButton, "addTaskButton").isEnabled()

    panel.close()
    app.quit()


def test_conversion_panel_directory_input_uses_directory_selection(monkeypatch):
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()
    panel.findChild(QComboBox, "inputTypeCombo").setCurrentText("目录批量")

    monkeypatch.setattr(
        "texbook.gui.main_panel.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: r"\\server\share\pdfs",
    )

    panel.findChild(QToolButton, "pdfInputBrowseButton").click()

    assert panel.selection_state.input_selection.kind == GuiInputKind.directory
    assert panel.selection_state.input_selection.paths == (r"\\server\share\pdfs",)
    assert panel.findChild(QLineEdit, "pdfInputField").text() == r"\\server\share\pdfs"

    panel.close()
    app.quit()


def test_conversion_panel_switching_input_type_clears_previous_input_only():
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()
    panel.set_input_selection(GuiInputSelection.from_single_file(r"C:\docs\a.pdf"))
    panel.set_output_directory(r"D:\tex-output")

    assert panel.findChild(QPushButton, "addTaskButton").isEnabled()

    panel.findChild(QComboBox, "inputTypeCombo").setCurrentText("目录批量")

    assert panel.selection_state.input_selection.kind == GuiInputKind.directory
    assert panel.selection_state.input_selection.paths == ()
    assert panel.selection_state.output_directory == r"D:\tex-output"
    assert panel.findChild(QLineEdit, "pdfInputField").text() == ""
    assert not panel.findChild(QPushButton, "addTaskButton").isEnabled()

    panel.close()
    app.quit()


def test_main_window_status_bar_tracks_path_selection_state():
    app = create_application(["texbook-gui-test"])
    window = MainWindow()
    panel = window.centralWidget()

    assert window.statusBar().currentMessage() == "请选择 PDF 输入和产物目录"

    panel.set_input_selection(GuiInputSelection.from_single_file(r"C:\docs\a.pdf"))
    assert window.statusBar().currentMessage() == "已选择 PDF 输入，请选择产物目录"

    panel.set_output_directory(r"D:\tex-output")
    assert window.statusBar().currentMessage() == "已选择 PDF 输入和产物目录"

    window.close()
    app.quit()
