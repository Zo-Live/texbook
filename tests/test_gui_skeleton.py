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
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QToolButton,
    QWidget,
)

from texbook.document_class import DocumentClassMode  # noqa: E402
from texbook.gui.app import create_application  # noqa: E402
from texbook.gui.core_adapter import build_core_conversion_bundle  # noqa: E402
from texbook.gui.main_panel import ConversionMainPanel  # noqa: E402
from texbook.gui.main_window import MainWindow  # noqa: E402
from texbook.gui.resources import (  # noqa: E402
    APP_DISPLAY_NAME,
    APP_ORGANIZATION_NAME,
    APP_WINDOW_TITLE,
    resolve_app_icon_path,
)
from texbook.gui.selection import GuiInputKind, GuiInputSelection, GuiPathSelectionState  # noqa: E402
from texbook.gui.settings import GuiConversionMode, GuiConversionSettings, GuiOutputKind  # noqa: E402
from texbook.gui.tasks import (  # noqa: E402
    GuiTaskRuntimeUpdate,
    GuiTaskStage,
    GuiTaskStatus,
    apply_progress_event,
    create_task_view_state,
    create_conversion_tasks,
    mark_task_completed,
    mark_task_failed,
    mark_task_running,
)
from texbook.llm.scheduler import ProgressEvent  # noqa: E402
from texbook.output_options import BeamerBoxStyle, CtexFontProfile  # noqa: E402
from texbook.structure import StructureMode  # noqa: E402


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
        "outputKindCombo",
        "batchPatternField",
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
        "taskListScrollArea",
        "taskRowsContainer",
    ]:
        assert panel.findChild(QWidget, object_name) is not None

    panel.close()
    app.quit()


def test_conversion_panel_default_settings_match_cli_defaults():
    app = create_application(["texbook-gui-test"])
    panel = ConversionMainPanel()

    settings = panel.current_settings()

    assert settings.conversion_mode == GuiConversionMode.tex_file
    assert settings.output_kind == GuiOutputKind.tex_file
    assert settings.confirm_overwrite is True
    assert settings.batch_pattern == "*.pdf"
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
            batch_pattern="slides-*.pdf",
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
    assert settings.output_kind == GuiOutputKind.project
    assert settings.confirm_overwrite is False
    assert settings.batch_pattern == "slides-*.pdf"
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
    assert panel.findChild(QLineEdit, "batchPatternField").isEnabled() is False

    panel.findChild(QComboBox, "outputKindCombo").setCurrentText("目录化项目")

    assert panel.current_settings().conversion_mode == GuiConversionMode.project
    assert panel.findChild(QComboBox, "structureModeCombo").isEnabled() is True
    assert panel.findChild(QSpinBox, "structureChunkPagesSpinBox").isEnabled() is True
    assert panel.findChild(QSpinBox, "batchWorkersSpinBox").isEnabled() is False

    panel.findChild(QComboBox, "inputTypeCombo").setCurrentText("目录批量")

    assert panel.current_settings().conversion_mode == GuiConversionMode.project
    assert panel.findChild(QComboBox, "structureModeCombo").isEnabled() is True
    assert panel.findChild(QSpinBox, "batchWorkersSpinBox").isEnabled() is True
    assert panel.findChild(QLineEdit, "batchPatternField").isEnabled() is True

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
        "texbook.gui.main_panel.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (r"D:\tex-output\lecture.tex", "LaTeX 文件 (*.tex)"),
    )

    panel.findChild(QToolButton, "pdfInputBrowseButton").click()

    assert panel.selection_state.input_selection.kind == GuiInputKind.single_file
    assert panel.selection_state.input_selection.paths == (r"C:\books\lecture.pdf",)
    assert panel.findChild(QLineEdit, "pdfInputField").text() == r"C:\books\lecture.pdf"
    assert not panel.findChild(QPushButton, "addTaskButton").isEnabled()

    panel.findChild(QToolButton, "outputBrowseButton").click()

    assert panel.selection_state.output_directory == r"D:\tex-output\lecture.tex"
    assert panel.findChild(QLineEdit, "outputDirectoryField").text() == r"D:\tex-output\lecture.tex"
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


def test_gui_core_adapter_maps_settings_to_core_options(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXBOOK_MODEL", "env-model")
    monkeypatch.setenv("TEXBOOK_API_KEY", "env-key")
    settings = GuiConversionSettings(
        pages="1,3-4",
        document_class="ctexbeamer",
        structure_mode="llm",
        structure_chunk_pages=6,
        structure_max_pages=42,
        manual_title="手动标题",
        title_source="filename",
        show_date=True,
        beamer_title_page=False,
        prompt_preset="chinese-math",
        extra_prompt="只提取公式",
        temperature=0.5,
        timeout_seconds=30.0,
        max_tokens=64000,
        cache_enabled=True,
        cache_directory=str(tmp_path / "cache"),
        clear_cache=True,
        chunk_pages=3,
        prefetch_chunks=2,
        llm_max_concurrency=2,
        llm_min_request_interval=1.5,
        image_dpi=180,
        image_dpi_min=120,
        image_dpi_max=240,
        image_format="jpeg",
        jpeg_quality=92,
        llm_retries=4,
        llm_retry_initial_delay=3.0,
        llm_retry_max_delay=40.0,
        beamer_box_style="tcolorbox",
        ctex_font_profile="local",
    )

    bundle = build_core_conversion_bundle(settings, repo_root=ROOT)

    assert bundle.llm_config.model == "env-model"
    assert bundle.llm_config.api_key == "env-key"
    assert bundle.pages == [1, 3, 4]
    assert bundle.conversion_options.document_class == DocumentClassMode.ctexbeamer
    assert bundle.conversion_options.structure_options.mode == StructureMode.llm
    assert bundle.conversion_options.manual_title == "手动标题"
    assert bundle.conversion_options.cache_options.cache_dir == tmp_path / "cache"
    assert bundle.conversion_options.cache_options.clear is True
    assert bundle.conversion_options.image_options.image_format == "jpeg"
    assert bundle.conversion_options.output_options.beamer_box_style == BeamerBoxStyle.tcolorbox
    assert bundle.conversion_options.output_options.ctex_font_profile == CtexFontProfile.local
    assert bundle.conversion_options.output_options.beamer_title_page is False
    assert bundle.conversion_options.retry_options.retries == 4
    assert bundle.conversion_options.llm_max_concurrency == 2


def test_create_tasks_for_single_file_tex_and_project(monkeypatch):
    monkeypatch.setenv("TEXBOOK_MODEL", "model")
    monkeypatch.setenv("TEXBOOK_API_KEY", "key")
    base = GuiConversionSettings(
        path_state=GuiPathSelectionState(
            input_selection=GuiInputSelection.from_single_file("lecture.pdf"),
            output_directory="out/lecture",
        )
    )

    tex_task = create_conversion_tasks(base, repo_root=ROOT)[0]
    project_task = create_conversion_tasks(
        GuiConversionSettings(
            path_state=base.path_state,
            output_kind=GuiOutputKind.project,
        ),
        repo_root=ROOT,
    )[0]

    assert tex_task.source_pdf == Path("lecture.pdf")
    assert tex_task.output_target.kind == GuiOutputKind.tex_file
    assert tex_task.output_target.path == Path("out/lecture.tex")
    assert project_task.output_target.kind == GuiOutputKind.project
    assert project_task.output_target.path == Path("out/lecture")
    assert tex_task.status == GuiTaskStatus.pending


def test_task_view_state_tracks_runtime_updates_and_progress_events(monkeypatch):
    monkeypatch.setenv("TEXBOOK_MODEL", "model")
    monkeypatch.setenv("TEXBOOK_API_KEY", "key")
    task = create_conversion_tasks(
        GuiConversionSettings(
            path_state=GuiPathSelectionState(
                input_selection=GuiInputSelection.from_single_file("lecture.pdf"),
                output_directory="out/lecture",
            )
        ),
        repo_root=ROOT,
    )[0]

    state = create_task_view_state(task)
    assert state.status == GuiTaskStatus.pending
    assert state.stage == GuiTaskStage.waiting
    assert state.progress == 0

    mark_task_running(state)
    assert state.status == GuiTaskStatus.running
    assert state.progress == 5

    apply_progress_event(
        state,
        ProgressEvent(kind="stage_started", operation="chunk", label="chunk 1/2"),
    )
    assert state.stage == GuiTaskStage.chunk
    assert state.progress == 45

    apply_progress_event(
        state,
        ProgressEvent(
            kind="cache_hit",
            operation="chunk",
            label="chunk 1/2",
            metadata={"chunk_index": 1, "total_chunks": 2},
        ),
    )
    assert state.cache_hits == 1

    apply_progress_event(
        state,
        ProgressEvent(
            kind="retry_scheduled",
            operation="chunk",
            label="chunk 2/2",
            delay=0.5,
            error="timeout",
        ),
    )
    assert state.retries == 1

    apply_progress_event(
        state,
        ProgressEvent(
            kind="stage_completed",
            operation="chunk",
            label="chunk 2/2",
            metadata={"chunk_index": 2, "total_chunks": 2},
        ),
    )
    assert state.progress == 85

    mark_task_completed(state, result="out/lecture.tex", notes=("完成",))
    assert state.status == GuiTaskStatus.completed
    assert state.progress == 100
    assert state.result == "out/lecture.tex"

    mark_task_failed(state, "LLM failed")
    assert state.status == GuiTaskStatus.failed
    assert state.stage == GuiTaskStage.failed
    assert state.error == "LLM failed"


def test_conversion_panel_adds_visual_task_rows_and_updates_progress(monkeypatch):
    monkeypatch.setenv("TEXBOOK_MODEL", "model")
    monkeypatch.setenv("TEXBOOK_API_KEY", "key")
    app = create_application(["texbook-gui-test"])
    window = MainWindow()
    panel = window.centralWidget()
    assert isinstance(panel, ConversionMainPanel)

    panel.set_input_selection(GuiInputSelection.from_multiple_files(["a.pdf", "b.pdf"]))
    panel.set_output_directory("out")
    panel.findChild(QPushButton, "addTaskButton").click()

    states = panel.task_view_states()
    assert len(states) == 2
    assert panel.findChild(QWidget, f"taskRow_{states[0].task_id}") is not None
    assert panel.findChild(QLabel, f"taskStatusBadge_{states[0].task_id}").text() == "待处理"
    assert panel.findChild(QLabel, f"taskStageLabel_{states[0].task_id}").text() == "阶段：等待中"
    assert panel.findChild(QLabel, f"taskCacheLabel_{states[0].task_id}").text() == "缓存命中 0"
    assert panel.findChild(QLabel, f"taskRetryLabel_{states[0].task_id}").text() == "重试 0"
    assert panel.findChild(QLabel, "taskEmptyStatusLabel").text() == "已创建 2 个任务"
    assert panel.findChild(QPushButton, "startButton").isEnabled() is True

    first_id = states[0].task_id
    panel.handle_task_progress(
        first_id,
        ProgressEvent(
            kind="stage_completed",
            operation="chunk",
            label="chunk 1/2",
            metadata={"chunk_index": 1, "total_chunks": 2},
        ),
    )
    panel.handle_task_progress(
        first_id,
        ProgressEvent(kind="cache_hit", operation="chunk", label="chunk 1/2"),
    )
    panel.update_task_state(
        first_id,
        GuiTaskRuntimeUpdate(status=GuiTaskStatus.completed, stage=GuiTaskStage.completed, progress=100, result="out/a.tex"),
    )

    assert panel.findChild(QLabel, f"taskStatusBadge_{first_id}").text() == "完成"
    assert panel.findChild(QLabel, f"taskCacheLabel_{first_id}").text() == "缓存命中 1"
    assert panel.findChild(QLabel, f"taskResultLabel_{first_id}").text() == "完成结果：out/a.tex"
    assert panel.findChild(QProgressBar, "overallProgressBar").value() == 50

    panel.update_task_state(
        states[1].task_id,
        GuiTaskRuntimeUpdate(status=GuiTaskStatus.failed, stage=GuiTaskStage.failed, progress=40, error="LLM failed"),
    )
    assert panel.findChild(QLabel, f"taskStatusBadge_{states[1].task_id}").text() == "失败"
    assert panel.findChild(QLabel, f"taskResultLabel_{states[1].task_id}").text() == "失败原因：LLM failed"
    assert panel.findChild(QProgressBar, "overallProgressBar").value() == 70

    window.close()
    app.quit()


def test_conversion_panel_start_button_only_reports_future_execution(monkeypatch):
    monkeypatch.setenv("TEXBOOK_MODEL", "model")
    monkeypatch.setenv("TEXBOOK_API_KEY", "key")
    app = create_application(["texbook-gui-test"])
    window = MainWindow()
    panel = window.centralWidget()
    assert isinstance(panel, ConversionMainPanel)

    panel.set_input_selection(GuiInputSelection.from_single_file("lecture.pdf"))
    panel.set_output_directory("out/lecture")
    panel.findChild(QPushButton, "addTaskButton").click()
    panel.findChild(QPushButton, "startButton").click()

    assert window.statusBar().currentMessage() == "后台执行将在后续阶段接入。"

    window.close()
    app.quit()


def test_create_tasks_supports_multiple_pdf_project_output(monkeypatch):
    monkeypatch.setenv("TEXBOOK_MODEL", "model")
    monkeypatch.setenv("TEXBOOK_API_KEY", "key")
    settings = GuiConversionSettings(
        path_state=GuiPathSelectionState(
            input_selection=GuiInputSelection.from_multiple_files(["a.pdf", "b.PDF"]),
            output_directory="out",
        ),
        output_kind=GuiOutputKind.project,
        batch_workers=2,
    )

    tasks = create_conversion_tasks(settings, repo_root=ROOT)

    assert [task.source_pdf for task in tasks] == [Path("a.pdf"), Path("b.PDF")]
    assert [task.output_target.path for task in tasks] == [Path("out/a"), Path("out/b")]
    assert all(task.output_target.kind == GuiOutputKind.project for task in tasks)


def test_create_tasks_uses_windows_file_stems_for_native_paths(monkeypatch):
    monkeypatch.setenv("TEXBOOK_MODEL", "model")
    monkeypatch.setenv("TEXBOOK_API_KEY", "key")
    settings = GuiConversionSettings(
        path_state=GuiPathSelectionState(
            input_selection=GuiInputSelection.from_multiple_files(
                [r"C:\books\a.pdf", r"\\server\share\b.PDF"]
            ),
            output_directory="out",
        ),
        output_kind=GuiOutputKind.tex_file,
    )

    tasks = create_conversion_tasks(settings, repo_root=ROOT)

    assert [task.label for task in tasks] == ["a.pdf", "b.PDF"]
    assert [task.output_target.path for task in tasks] == [Path("out/a.tex"), Path("out/b.tex")]


def test_create_tasks_expands_directory_pattern(tmp_path, monkeypatch):
    monkeypatch.setenv("TEXBOOK_MODEL", "model")
    monkeypatch.setenv("TEXBOOK_API_KEY", "key")
    (tmp_path / "slides-2.pdf").write_text("", encoding="utf-8")
    (tmp_path / "slides-1.pdf").write_text("", encoding="utf-8")
    (tmp_path / "ignore.pdf").write_text("", encoding="utf-8")
    (tmp_path / "slides.txt").write_text("", encoding="utf-8")
    settings = GuiConversionSettings(
        path_state=GuiPathSelectionState(
            input_selection=GuiInputSelection.from_directory(str(tmp_path)),
            output_directory=str(tmp_path / "out"),
        ),
        output_kind=GuiOutputKind.tex_file,
        batch_pattern="slides-*.pdf",
    )

    tasks = create_conversion_tasks(settings, repo_root=ROOT)

    assert [task.source_pdf.name for task in tasks] == ["slides-1.pdf", "slides-2.pdf"]
    assert [task.output_target.path.name for task in tasks] == ["slides-1.tex", "slides-2.tex"]
