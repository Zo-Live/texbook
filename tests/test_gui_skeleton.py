"""Tests for the GUI application skeleton."""

from __future__ import annotations

import os
from pathlib import Path
import runpy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QSpinBox,
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
from texbook.gui.settings import GuiConversionMode, GuiConversionSettings  # noqa: E402


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
        "pageOptionsPanel",
        "pagesField",
        "manualTitleField",
        "titleSourceCombo",
        "documentClassCombo",
        "structureModeCombo",
        "structureChunkPagesSpinBox",
        "structureMaxPagesSpinBox",
        "beamerTitlePageCheckBox",
        "showDateCheckBox",
        "modelField",
        "baseUrlField",
        "apiKeyField",
        "promptPresetCombo",
        "extraPromptEdit",
        "cacheEnabledCheckBox",
        "cacheDirectoryField",
        "cacheBrowseButton",
        "clearCacheCheckBox",
        "chunkPagesSpinBox",
        "prefetchChunksSpinBox",
        "llmConcurrencySpinBox",
        "llmIntervalSpinBox",
        "batchWorkersSpinBox",
        "advancedOptionsPanel",
        "imageDpiSpinBox",
        "imageDpiMinSpinBox",
        "imageDpiMaxSpinBox",
        "imageFormatCombo",
        "jpegQualitySpinBox",
        "llmRetriesSpinBox",
        "llmRetryInitialDelaySpinBox",
        "llmRetryMaxDelaySpinBox",
        "timeoutSpinBox",
        "temperatureSpinBox",
        "maxTokensSpinBox",
        "beamerBoxStyleCombo",
        "ctexFontProfileCombo",
        "overallProgressBar",
        "taskEmptyStatusLabel",
    ]:
        assert panel.findChild(QWidget, object_name) is not None

    panel.close()
    app.quit()


def test_conversion_panel_default_settings_match_cli_defaults():
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()

    settings = panel.current_settings()

    assert settings.conversion_mode == GuiConversionMode.single_file
    assert settings.confirm_overwrite is True
    assert settings.pages == ""
    assert settings.document_class == "auto"
    assert settings.structure_mode == "auto"
    assert settings.structure_chunk_pages == 8
    assert settings.structure_max_pages == 32
    assert settings.manual_title == ""
    assert settings.title_source == "filename"
    assert settings.show_date is False
    assert settings.beamer_title_page is True
    assert settings.prompt_preset == "chinese-math"
    assert settings.temperature == 1.0
    assert settings.timeout_seconds is None
    assert settings.max_tokens == 128000
    assert settings.cache_enabled is True
    assert settings.cache_directory == "build/.texbook_cache"
    assert settings.clear_cache is False
    assert settings.chunk_pages == 4
    assert settings.prefetch_chunks == 1
    assert settings.llm_max_concurrency == 1
    assert settings.llm_min_request_interval == 0.0
    assert settings.batch_workers == 1
    assert settings.image_dpi == 160
    assert settings.image_dpi_min == 100
    assert settings.image_dpi_max is None
    assert settings.image_format == "png"
    assert settings.jpeg_quality == 85
    assert settings.llm_retries == 2
    assert settings.llm_retry_initial_delay == 2.0
    assert settings.llm_retry_max_delay == 30.0
    assert settings.beamer_box_style == "block"
    assert settings.ctex_font_profile == "default"
    assert panel.validate_settings() == []
    assert panel.findChild(QComboBox, "promptPresetCombo").isEditable() is True

    panel.close()
    app.quit()


def test_conversion_panel_settings_round_trip_preserves_all_fields():
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()
    panel.set_settings(
        GuiConversionSettings(
            conversion_mode=GuiConversionMode.project,
            confirm_overwrite=False,
            pages="1,3-5",
            document_class="ctexbeamer",
            structure_mode="llm",
            structure_chunk_pages=6,
            structure_max_pages=48,
            manual_title="手动标题",
            title_source="filename",
            show_date=True,
            beamer_title_page=False,
            model="vision-model",
            base_url="https://api.example/v1",
            api_key="secret",
            prompt_preset="chinese-math",
            extra_prompt="只提取公式",
            temperature=0.7,
            timeout_seconds=120.0,
            max_tokens=64000,
            cache_enabled=True,
            cache_directory=r"D:\tex-cache",
            clear_cache=True,
            chunk_pages=3,
            prefetch_chunks=2,
            llm_max_concurrency=2,
            llm_min_request_interval=1.5,
            batch_workers=4,
            image_dpi=180,
            image_dpi_min=120,
            image_dpi_max=240,
            image_format="jpeg",
            jpeg_quality=92,
            llm_retries=4,
            llm_retry_initial_delay=3.5,
            llm_retry_max_delay=45.0,
            beamer_box_style="tcolorbox",
            ctex_font_profile="local",
        )
    )

    settings = panel.current_settings()

    assert settings.conversion_mode == GuiConversionMode.project
    assert settings.confirm_overwrite is False
    assert settings.pages == "1,3-5"
    assert settings.document_class == "ctexbeamer"
    assert settings.structure_mode == "llm"
    assert settings.structure_chunk_pages == 6
    assert settings.structure_max_pages == 48
    assert settings.manual_title == "手动标题"
    assert settings.title_source == "filename"
    assert settings.show_date is True
    assert settings.beamer_title_page is False
    assert settings.model == "vision-model"
    assert settings.base_url == "https://api.example/v1"
    assert settings.api_key == "secret"
    assert settings.extra_prompt == "只提取公式"
    assert settings.temperature == 0.7
    assert settings.timeout_seconds == 120.0
    assert settings.max_tokens == 64000
    assert settings.cache_directory == r"D:\tex-cache"
    assert settings.clear_cache is True
    assert settings.chunk_pages == 3
    assert settings.prefetch_chunks == 2
    assert settings.llm_max_concurrency == 2
    assert settings.llm_min_request_interval == 1.5
    assert settings.batch_workers == 4
    assert settings.image_dpi == 180
    assert settings.image_dpi_min == 120
    assert settings.image_dpi_max == 240
    assert settings.image_format == "jpeg"
    assert settings.jpeg_quality == 92
    assert settings.llm_retries == 4
    assert settings.llm_retry_initial_delay == 3.5
    assert settings.llm_retry_max_delay == 45.0
    assert settings.beamer_box_style == "tcolorbox"
    assert settings.ctex_font_profile == "local"

    panel.close()
    app.quit()


def test_conversion_panel_validates_pages_and_title_conflict():
    app = create_application(["texbook-gui-test"])
    window = MainWindow()
    panel = window.centralWidget()

    panel.findChild(QLineEdit, "pagesField").setText("5-3")

    assert "页面范围格式无效" in panel.validate_settings()[0]
    assert window.statusBar().currentMessage().startswith("页面范围格式无效")

    panel.findChild(QLineEdit, "pagesField").setText("1,3-5")
    panel.findChild(QLineEdit, "manualTitleField").setText("手动标题")
    panel.findChild(QComboBox, "titleSourceCombo").setCurrentText("llm")

    assert panel.findChild(QLineEdit, "manualTitleField").isEnabled() is False
    assert "手动标题不能与 LLM 标题来源同时使用。" in panel.validate_settings()

    window.close()
    app.quit()


def test_conversion_panel_option_dependencies_follow_mode_cache_and_image_format():
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()

    assert panel.findChild(QComboBox, "structureModeCombo").isEnabled() is False
    assert panel.findChild(QSpinBox, "structureChunkPagesSpinBox").isEnabled() is False
    assert panel.findChild(QSpinBox, "batchWorkersSpinBox").isEnabled() is False

    panel.findChild(QRadioButton, "projectModeRadio").click()

    assert panel.current_settings().conversion_mode == GuiConversionMode.project
    assert panel.findChild(QComboBox, "structureModeCombo").isEnabled() is True
    assert panel.findChild(QSpinBox, "structureChunkPagesSpinBox").isEnabled() is True
    assert panel.findChild(QSpinBox, "batchWorkersSpinBox").isEnabled() is False

    panel.findChild(QRadioButton, "batchModeRadio").click()

    assert panel.current_settings().conversion_mode == GuiConversionMode.batch
    assert panel.findChild(QComboBox, "structureModeCombo").isEnabled() is False
    assert panel.findChild(QSpinBox, "batchWorkersSpinBox").isEnabled() is True

    panel.findChild(QCheckBox, "clearCacheCheckBox").setChecked(True)
    assert panel.current_settings().clear_cache is True

    panel.findChild(QCheckBox, "cacheEnabledCheckBox").setChecked(False)

    assert panel.findChild(QLineEdit, "cacheDirectoryField").isEnabled() is False
    assert panel.findChild(QToolButton, "cacheBrowseButton").isEnabled() is False
    assert panel.findChild(QCheckBox, "clearCacheCheckBox").isEnabled() is False
    assert panel.current_settings().clear_cache is False

    panel.findChild(QComboBox, "imageFormatCombo").setCurrentText("png")

    assert panel.findChild(QSpinBox, "jpegQualitySpinBox").isEnabled() is False

    panel.findChild(QComboBox, "imageFormatCombo").setCurrentText("jpeg")

    assert panel.findChild(QSpinBox, "jpegQualitySpinBox").isEnabled() is True

    panel.close()
    app.quit()


def test_conversion_panel_cache_directory_browse_updates_settings(monkeypatch):
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()

    monkeypatch.setattr(
        "texbook.gui.main_panel.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: r"D:\tex-cache",
    )

    panel.findChild(QToolButton, "cacheBrowseButton").click()

    assert panel.findChild(QLineEdit, "cacheDirectoryField").text() == r"D:\tex-cache"
    assert panel.current_settings().cache_directory == r"D:\tex-cache"

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
