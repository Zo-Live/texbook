"""Main conversion panel for the TexBook GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from texbook.gui.executor import GuiOverwriteConfirmationRequest, GuiTaskExecutor
from texbook.gui.resources import APP_DISPLAY_NAME
from texbook.gui.selection import (
    GuiInputKind,
    GuiInputSelection,
    GuiPathSelectionState,
    input_kind_from_label,
)
from texbook.gui.settings import (
    GuiConversionMode,
    GuiOutputKind,
    GuiConversionSettings,
    validate_gui_settings,
)
from texbook.gui.tasks import (
    GuiTaskCreationError,
    GuiTaskRuntimeUpdate,
    GuiTaskStatus,
    GuiTaskViewState,
    TERMINAL_TASK_STATUSES,
    apply_progress_event,
    apply_task_update,
    create_conversion_tasks,
    create_task_view_state,
    mark_task_canceling,
    mark_task_canceled,
    mark_task_completed,
    mark_task_failed,
    mark_task_running,
)
from texbook.gui.widgets import InlineField, MetricPill, OptionGrid, SectionPanel
from texbook.llm.scheduler import ProgressEvent


class ConversionMainPanel(QWidget):
    """Fluent Design main panel shown when the GUI opens."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("conversionMainPanel")
        self.selection_state = GuiPathSelectionState()
        self.tasks = []
        self._task_states: dict[str, GuiTaskViewState] = {}
        self._task_rows: dict[str, QFrame] = {}
        self._executor: GuiTaskExecutor | None = None
        self._executor_factory = GuiTaskExecutor

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(self._create_command_bar())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._create_settings_scroll(), 3)
        content.addWidget(self._create_task_list_panel(), 2)
        layout.addLayout(content, 1)

        self._connect_selection_controls()
        self._refresh_path_state()

    def _create_command_bar(self) -> QFrame:
        command_bar = QFrame(self)
        command_bar.setObjectName("topCommandBar")
        layout = QHBoxLayout(command_bar)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        title_group = QVBoxLayout()
        title_group.setSpacing(2)

        title = QLabel(APP_DISPLAY_NAME, command_bar)
        title.setObjectName("appTitleLabel")
        title_group.addWidget(title)

        subtitle = QLabel("PDF 转 LaTeX 转换工具", command_bar)
        subtitle.setObjectName("appSubtitleLabel")
        title_group.addWidget(subtitle)

        layout.addLayout(title_group, 1)
        layout.addWidget(self._make_tool_button("themeButton", "浅色", QStyle.StandardPixmap.SP_DesktopIcon))
        layout.addWidget(
            self._make_tool_button(
                "languageButton",
                "中文",
                QStyle.StandardPixmap.SP_FileDialogDetailedView,
            )
        )

        add_task = QPushButton("添加任务", command_bar)
        add_task.setObjectName("addTaskButton")
        add_task.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        add_task.setToolTip("选择 PDF 输入和产物目录后可添加任务。")
        add_task.setEnabled(False)
        self.add_task_button = add_task
        layout.addWidget(add_task)

        start = QPushButton("开始转换", command_bar)
        start.setObjectName("startButton")
        start.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        start.setToolTip("开始执行队列中的待处理任务。")
        start.setEnabled(False)
        self.start_button = start
        layout.addWidget(start)

        return command_bar

    def _create_settings_scroll(self) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setObjectName("settingsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        pane = QWidget(scroll)
        pane.setObjectName("settingsPane")
        pane.setMinimumWidth(560)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._create_input_panel())
        layout.addWidget(self._create_output_panel())
        parameters = QWidget(pane)
        parameters.setObjectName("parametersPanel")
        parameters_layout = QVBoxLayout(parameters)
        parameters_layout.setContentsMargins(0, 0, 0, 0)
        parameters_layout.setSpacing(12)
        parameters_layout.addWidget(self._create_page_document_panel())
        parameters_layout.addWidget(self._create_document_panel())
        parameters_layout.addWidget(self._create_model_panel())
        parameters_layout.addWidget(self._create_cache_panel())
        parameters_layout.addWidget(self._create_advanced_panel())
        layout.addWidget(parameters)

        layout.addStretch(1)
        scroll.setWidget(pane)
        return scroll

    def _create_input_panel(self) -> SectionPanel:
        panel = SectionPanel("输入", object_name="inputPanel", parent=self)
        grid = OptionGrid(parent=panel)

        pdf_input = QLineEdit(panel)
        pdf_input.setObjectName("pdfInputField")
        pdf_input.setPlaceholderText("选择 PDF 文件或目录")
        pdf_input.setReadOnly(True)
        self.pdf_input_field = pdf_input
        browse = self._make_icon_button(
            "pdfInputBrowseButton",
            QStyle.StandardPixmap.SP_DialogOpenButton,
            "浏览 PDF 输入",
        )
        self.pdf_input_browse_button = browse
        grid.add_row("PDF 输入", InlineField(pdf_input, browse, parent=panel))

        input_type = QComboBox(panel)
        input_type.setObjectName("inputTypeCombo")
        input_type.addItems(["单个 PDF", "多个 PDF", "目录批量"])
        self.input_type_combo = input_type
        grid.add_row("输入类型", input_type)

        batch_pattern = QLineEdit(panel)
        batch_pattern.setObjectName("batchPatternField")
        batch_pattern.setPlaceholderText("*.pdf")
        batch_pattern.setText("*.pdf")
        self.batch_pattern_field = batch_pattern
        grid.add_row("批量匹配", batch_pattern)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_output_panel(self) -> SectionPanel:
        panel = SectionPanel("输出", object_name="outputPanel", parent=self)
        grid = OptionGrid(parent=panel)

        output_kind = QComboBox(panel)
        output_kind.setObjectName("outputKindCombo")
        output_kind.addItems(["单个 .tex", "目录化项目"])
        self.output_kind_combo = output_kind
        grid.add_row("输出形式", output_kind)

        output_dir = QLineEdit(panel)
        output_dir.setObjectName("outputDirectoryField")
        output_dir.setPlaceholderText("选择输出目标")
        output_dir.setReadOnly(True)
        self.output_directory_field = output_dir
        browse = self._make_icon_button(
            "outputBrowseButton",
            QStyle.StandardPixmap.SP_DirOpenIcon,
            "浏览输出目标",
        )
        self.output_browse_button = browse
        self.output_target_label = "输出目标"
        grid.add_row("输出目标", InlineField(output_dir, browse, parent=panel))

        overwrite = QCheckBox("覆盖前确认", panel)
        overwrite.setObjectName("confirmOverwriteCheckBox")
        overwrite.setChecked(True)
        self.confirm_overwrite_checkbox = overwrite
        grid.add_row("写盘策略", overwrite)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_page_document_panel(self) -> SectionPanel:
        panel = SectionPanel("页面范围", object_name="pageOptionsPanel", parent=self)
        grid = OptionGrid(parent=panel)

        pages = QLineEdit(panel)
        pages.setObjectName("pagesField")
        pages.setPlaceholderText("全部页面")
        self.pages_field = pages
        grid.add_row("页面范围", pages)

        manual_title = QLineEdit(panel)
        manual_title.setObjectName("manualTitleField")
        manual_title.setPlaceholderText("默认使用 PDF 文件名")
        self.manual_title_field = manual_title
        grid.add_row("手动标题", manual_title)

        title_source = QComboBox(panel)
        title_source.setObjectName("titleSourceCombo")
        title_source.addItems(["filename", "llm"])
        self.title_source_combo = title_source
        grid.add_row("标题来源", title_source)

        show_date = QCheckBox("显示日期", panel)
        show_date.setObjectName("showDateCheckBox")
        self.show_date_checkbox = show_date
        grid.add_row("日期", show_date)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_document_panel(self) -> SectionPanel:
        panel = SectionPanel("文档类", object_name="documentOptionsPanel", parent=self)
        grid = OptionGrid(parent=panel)

        document_class = QComboBox(panel)
        document_class.setObjectName("documentClassCombo")
        document_class.addItems(
            ["auto", "ctexart", "ctexbook", "ctexbeamer", "article", "book", "beamer"]
        )
        self.document_class_combo = document_class
        grid.add_row("文档类", document_class)

        structure = QComboBox(panel)
        structure.setObjectName("structureModeCombo")
        structure.addItems(["auto", "off", "local", "llm"])
        self.structure_mode_combo = structure
        grid.add_row("结构规划", structure)

        structure_chunk_pages = self._make_spin_box("structureChunkPagesSpinBox", 1, 128, 8)
        self.structure_chunk_pages_spin_box = structure_chunk_pages
        grid.add_row("规划 Chunk 页数", structure_chunk_pages)

        structure_max_pages = self._make_spin_box("structureMaxPagesSpinBox", 1, 4096, 32)
        self.structure_max_pages_spin_box = structure_max_pages
        grid.add_row("规划最大页数", structure_max_pages)

        title_page = QCheckBox("生成 Beamer 标题页", panel)
        title_page.setObjectName("beamerTitlePageCheckBox")
        title_page.setChecked(True)
        self.beamer_title_page_checkbox = title_page
        grid.add_row("标题页", title_page)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_model_panel(self) -> SectionPanel:
        panel = SectionPanel("模型配置", object_name="modelOptionsPanel", parent=self)
        grid = OptionGrid(parent=panel)

        model = QLineEdit(panel)
        model.setObjectName("modelField")
        model.setPlaceholderText("TEXBOOK_MODEL")
        self.model_field = model
        grid.add_row("模型", model)

        base_url = QLineEdit(panel)
        base_url.setObjectName("baseUrlField")
        base_url.setPlaceholderText("TEXBOOK_BASE_URL")
        self.base_url_field = base_url
        grid.add_row("Base URL", base_url)

        api_key = QLineEdit(panel)
        api_key.setObjectName("apiKeyField")
        api_key.setEchoMode(QLineEdit.EchoMode.Password)
        api_key.setPlaceholderText("TEXBOOK_API_KEY")
        self.api_key_field = api_key
        grid.add_row("API Key", api_key)

        preset = QComboBox(panel)
        preset.setObjectName("promptPresetCombo")
        preset.setEditable(True)
        preset.addItem("chinese-math")
        self.prompt_preset_combo = preset
        grid.add_row("Prompt 预设", preset)

        extra_prompt = QTextEdit(panel)
        extra_prompt.setObjectName("extraPromptEdit")
        extra_prompt.setPlaceholderText("追加一次性转换要求")
        self.extra_prompt_edit = extra_prompt
        grid.add_row("额外要求", extra_prompt)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_cache_panel(self) -> SectionPanel:
        panel = SectionPanel("缓存与并发", object_name="cacheConcurrencyPanel", parent=self)
        grid = OptionGrid(parent=panel)

        cache_enabled = QCheckBox("启用缓存", panel)
        cache_enabled.setObjectName("cacheEnabledCheckBox")
        cache_enabled.setChecked(True)
        self.cache_enabled_checkbox = cache_enabled
        grid.add_row("缓存", cache_enabled)

        cache_dir = QLineEdit(panel)
        cache_dir.setObjectName("cacheDirectoryField")
        cache_dir.setPlaceholderText("build/.texbook_cache")
        cache_dir.setText("build/.texbook_cache")
        self.cache_directory_field = cache_dir
        browse = self._make_icon_button(
            "cacheBrowseButton",
            QStyle.StandardPixmap.SP_DirOpenIcon,
            "浏览缓存目录",
        )
        self.cache_browse_button = browse
        grid.add_row("缓存目录", InlineField(cache_dir, browse, parent=panel))

        clear_cache = QCheckBox("转换前清理匹配缓存", panel)
        clear_cache.setObjectName("clearCacheCheckBox")
        self.clear_cache_checkbox = clear_cache
        grid.add_row("清理缓存", clear_cache)

        chunk_pages = self._make_spin_box("chunkPagesSpinBox", 1, 64, 4)
        self.chunk_pages_spin_box = chunk_pages
        grid.add_row("Chunk 页数", chunk_pages)

        prefetch = self._make_spin_box("prefetchChunksSpinBox", 0, 16, 1)
        self.prefetch_chunks_spin_box = prefetch
        grid.add_row("预渲染", prefetch)

        llm_concurrency = self._make_spin_box("llmConcurrencySpinBox", 1, 16, 1)
        self.llm_concurrency_spin_box = llm_concurrency
        grid.add_row("LLM 并发", llm_concurrency)

        llm_interval = QDoubleSpinBox(panel)
        llm_interval.setObjectName("llmIntervalSpinBox")
        llm_interval.setRange(0.0, 600.0)
        llm_interval.setDecimals(1)
        llm_interval.setSingleStep(0.5)
        llm_interval.setValue(0.0)
        llm_interval.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self.llm_min_request_interval_spin_box = llm_interval
        grid.add_row("请求间隔", llm_interval)

        batch_workers = self._make_spin_box("batchWorkersSpinBox", 1, 16, 1)
        self.batch_workers_spin_box = batch_workers
        grid.add_row("批量 Worker", batch_workers)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_advanced_panel(self) -> SectionPanel:
        panel = SectionPanel("高级参数", object_name="advancedOptionsPanel", parent=self)
        grid = OptionGrid(parent=panel)

        image_dpi = self._make_spin_box("imageDpiSpinBox", 72, 600, 160)
        self.image_dpi_spin_box = image_dpi
        grid.add_row("图像 DPI", image_dpi)

        image_dpi_min = self._make_spin_box("imageDpiMinSpinBox", 1, 600, 100)
        self.image_dpi_min_spin_box = image_dpi_min
        grid.add_row("图像 DPI 下限", image_dpi_min)

        image_dpi_max = self._make_spin_box("imageDpiMaxSpinBox", 0, 600, 0)
        image_dpi_max.setSpecialValueText("默认 DPI")
        self.image_dpi_max_spin_box = image_dpi_max
        grid.add_row("图像 DPI 上限", image_dpi_max)

        image_format = QComboBox(panel)
        image_format.setObjectName("imageFormatCombo")
        image_format.addItems(["auto", "png", "jpeg"])
        image_format.setCurrentText("png")
        self.image_format_combo = image_format
        grid.add_row("图像格式", image_format)

        jpeg_quality = self._make_spin_box("jpegQualitySpinBox", 1, 100, 85)
        self.jpeg_quality_spin_box = jpeg_quality
        grid.add_row("JPEG 质量", jpeg_quality)

        retries = self._make_spin_box("llmRetriesSpinBox", 0, 10, 2)
        self.llm_retries_spin_box = retries
        grid.add_row("重试次数", retries)

        retry_initial_delay = QDoubleSpinBox(panel)
        retry_initial_delay.setObjectName("llmRetryInitialDelaySpinBox")
        retry_initial_delay.setRange(0.0, 600.0)
        retry_initial_delay.setDecimals(1)
        retry_initial_delay.setSingleStep(0.5)
        retry_initial_delay.setValue(2.0)
        retry_initial_delay.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self.llm_retry_initial_delay_spin_box = retry_initial_delay
        grid.add_row("初始重试延迟", retry_initial_delay)

        retry_max_delay = QDoubleSpinBox(panel)
        retry_max_delay.setObjectName("llmRetryMaxDelaySpinBox")
        retry_max_delay.setRange(0.0, 600.0)
        retry_max_delay.setDecimals(1)
        retry_max_delay.setSingleStep(0.5)
        retry_max_delay.setValue(30.0)
        retry_max_delay.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self.llm_retry_max_delay_spin_box = retry_max_delay
        grid.add_row("最大重试延迟", retry_max_delay)

        timeout = QDoubleSpinBox(panel)
        timeout.setObjectName("timeoutSpinBox")
        timeout.setRange(0.0, 6000.0)
        timeout.setDecimals(1)
        timeout.setSingleStep(1.0)
        timeout.setValue(0.0)
        timeout.setSpecialValueText("不限制")
        timeout.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        self.timeout_spin_box = timeout
        grid.add_row("LLM 超时", timeout)

        temperature = QDoubleSpinBox(panel)
        temperature.setObjectName("temperatureSpinBox")
        temperature.setRange(0.0, 2.0)
        temperature.setDecimals(2)
        temperature.setSingleStep(0.05)
        temperature.setValue(1.0)
        self.temperature_spin_box = temperature
        grid.add_row("Temperature", temperature)

        max_tokens = self._make_spin_box("maxTokensSpinBox", 1, 512000, 128000)
        self.max_tokens_spin_box = max_tokens
        grid.add_row("Max tokens", max_tokens)

        beamer_style = QComboBox(panel)
        beamer_style.setObjectName("beamerBoxStyleCombo")
        beamer_style.addItems(["block", "tcolorbox"])
        self.beamer_box_style_combo = beamer_style
        grid.add_row("Beamer 块", beamer_style)

        ctex_font = QComboBox(panel)
        ctex_font.setObjectName("ctexFontProfileCombo")
        ctex_font.addItems(["default", "local"])
        self.ctex_font_profile_combo = ctex_font
        grid.add_row("CTeX 字体", ctex_font)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_task_list_panel(self) -> SectionPanel:
        panel = SectionPanel("任务队列", object_name="taskListPanel", parent=self)
        panel.setMinimumWidth(330)
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(8)
        metrics.setVerticalSpacing(8)
        self.task_metric_labels = {}
        for index, (label, value, key) in enumerate(
            [
                ("待处理", "0", GuiTaskStatus.pending),
                ("运行中", "0", GuiTaskStatus.running),
                ("取消中", "0", GuiTaskStatus.canceling),
                ("已取消", "0", GuiTaskStatus.canceled),
                ("完成", "0", GuiTaskStatus.completed),
                ("失败", "0", GuiTaskStatus.failed),
            ]
        ):
            metric = MetricPill(label, value, parent=panel)
            self.task_metric_labels[key] = metric.findChildren(QLabel)[0]
            metrics.addWidget(metric, index // 2, index % 2)
        panel.body_layout.addLayout(metrics)

        body = QWidget(panel)
        body.setObjectName("taskListBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)
        self.task_list_body_layout = body_layout

        empty = QFrame(body)
        empty.setObjectName("taskEmptyState")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(18, 28, 18, 28)
        empty_layout.setSpacing(8)

        icon = QLabel("＋", empty)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setProperty("sectionTitle", True)
        empty_layout.addWidget(icon)

        title = QLabel("尚无转换任务", empty)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("sectionTitle", True)
        empty_layout.addWidget(title)

        status = QLabel("队列空闲", empty)
        status.setObjectName("taskEmptyStatusLabel")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setProperty("muted", True)
        empty_layout.addWidget(status)
        self.task_empty_state = empty

        body_layout.addWidget(empty)

        scroll = QScrollArea(body)
        scroll.setObjectName("taskListScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVisible(False)
        self.task_list_scroll_area = scroll

        rows = QWidget(scroll)
        rows.setObjectName("taskRowsContainer")
        rows_layout = QVBoxLayout(rows)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(8)
        rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.task_rows_container = rows
        self.task_rows_layout = rows_layout
        scroll.setWidget(rows)
        body_layout.addWidget(scroll, 1)

        progress = QProgressBar(body)
        progress.setObjectName("overallProgressBar")
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(False)
        self.overall_progress_bar = progress
        body_layout.addWidget(progress)
        body_layout.addStretch(1)

        panel.body_layout.addWidget(body, 1)
        return panel

    def _make_tool_button(
        self,
        object_name: str,
        text: str,
        standard_pixmap: QStyle.StandardPixmap,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(object_name)
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIcon(self.style().standardIcon(standard_pixmap))
        button.setEnabled(False)
        return button

    def _make_icon_button(
        self,
        object_name: str,
        standard_pixmap: QStyle.StandardPixmap,
        tooltip: str,
    ) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(object_name)
        button.setIcon(self.style().standardIcon(standard_pixmap))
        button.setToolTip(tooltip)
        button.setFixedWidth(34)
        return button

    def _make_spin_box(self, object_name: str, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin_box = QSpinBox(self)
        spin_box.setObjectName(object_name)
        spin_box.setRange(minimum, maximum)
        spin_box.setValue(value)
        spin_box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        return spin_box

    def _connect_selection_controls(self) -> None:
        self.pdf_input_browse_button.clicked.connect(self._browse_pdf_input)
        self.output_browse_button.clicked.connect(self._browse_output_directory)
        self.cache_browse_button.clicked.connect(self._browse_cache_directory)
        self.input_type_combo.currentTextChanged.connect(self._change_input_kind)
        self.output_kind_combo.currentTextChanged.connect(self._sync_gui_state)
        self.batch_pattern_field.textChanged.connect(self._sync_gui_state)
        self.add_task_button.clicked.connect(self.add_current_tasks)
        self.start_button.clicked.connect(self.start_pending_tasks)
        self.title_source_combo.currentTextChanged.connect(self._sync_gui_state)
        self.structure_mode_combo.currentTextChanged.connect(self._sync_gui_state)
        self.document_class_combo.currentTextChanged.connect(self._sync_gui_state)
        self.cache_enabled_checkbox.toggled.connect(self._sync_cache_controls)
        self.image_format_combo.currentTextChanged.connect(self._sync_image_controls)
        self.cache_directory_field.textChanged.connect(self._sync_gui_state)
        self.pages_field.textChanged.connect(self._sync_gui_state)
        self.manual_title_field.textChanged.connect(self._sync_gui_state)
        self.model_field.textChanged.connect(self._sync_gui_state)
        self.base_url_field.textChanged.connect(self._sync_gui_state)
        self.api_key_field.textChanged.connect(self._sync_gui_state)
        self.prompt_preset_combo.currentTextChanged.connect(self._sync_gui_state)
        self.extra_prompt_edit.textChanged.connect(self._sync_gui_state)
        self.confirm_overwrite_checkbox.toggled.connect(self._sync_gui_state)
        self.show_date_checkbox.toggled.connect(self._sync_gui_state)
        self.beamer_title_page_checkbox.toggled.connect(self._sync_gui_state)
        self.clear_cache_checkbox.toggled.connect(self._sync_gui_state)
        self.chunk_pages_spin_box.valueChanged.connect(self._sync_gui_state)
        self.prefetch_chunks_spin_box.valueChanged.connect(self._sync_gui_state)
        self.llm_concurrency_spin_box.valueChanged.connect(self._sync_gui_state)
        self.llm_min_request_interval_spin_box.valueChanged.connect(self._sync_gui_state)
        self.batch_workers_spin_box.valueChanged.connect(self._sync_gui_state)
        self.structure_chunk_pages_spin_box.valueChanged.connect(self._sync_gui_state)
        self.structure_max_pages_spin_box.valueChanged.connect(self._sync_gui_state)
        self.image_dpi_spin_box.valueChanged.connect(self._sync_gui_state)
        self.image_dpi_min_spin_box.valueChanged.connect(self._sync_gui_state)
        self.image_dpi_max_spin_box.valueChanged.connect(self._sync_gui_state)
        self.jpeg_quality_spin_box.valueChanged.connect(self._sync_gui_state)
        self.llm_retries_spin_box.valueChanged.connect(self._sync_gui_state)
        self.llm_retry_initial_delay_spin_box.valueChanged.connect(self._sync_gui_state)
        self.llm_retry_max_delay_spin_box.valueChanged.connect(self._sync_gui_state)
        self.timeout_spin_box.valueChanged.connect(self._sync_gui_state)
        self.temperature_spin_box.valueChanged.connect(self._sync_gui_state)
        self.max_tokens_spin_box.valueChanged.connect(self._sync_gui_state)
        self.beamer_box_style_combo.currentTextChanged.connect(self._sync_gui_state)
        self.ctex_font_profile_combo.currentTextChanged.connect(self._sync_gui_state)

        self._sync_image_controls()
        self._sync_cache_controls()
        self._sync_gui_state()

    def _browse_pdf_input(self) -> None:
        kind = self._current_input_kind()
        if kind == GuiInputKind.single_file:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "选择 PDF 文件",
                "",
                "PDF 文件 (*.pdf)",
            )
            if path:
                self.set_input_selection(GuiInputSelection.from_single_file(path))
            return

        if kind == GuiInputKind.multiple_files:
            paths, _selected_filter = QFileDialog.getOpenFileNames(
                self,
                "选择多个 PDF 文件",
                "",
                "PDF 文件 (*.pdf)",
            )
            if paths:
                self.set_input_selection(GuiInputSelection.from_multiple_files(paths))
            return

        directory = QFileDialog.getExistingDirectory(self, "选择 PDF 目录", "")
        if directory:
            self.set_input_selection(GuiInputSelection.from_directory(directory))

    def _browse_output_directory(self) -> None:
        if self._current_input_kind() == GuiInputKind.single_file and self._current_output_kind() == GuiOutputKind.tex_file:
            path, _selected_filter = QFileDialog.getSaveFileName(
                self,
                "选择输出 .tex 文件",
                "",
                "LaTeX 文件 (*.tex)",
            )
            if path:
                self.set_output_directory(path)
            return

        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", "")
        if directory:
            self.set_output_directory(directory)

    def _browse_cache_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择缓存目录", "")
        if directory:
            self.cache_directory_field.setText(directory)

    def _change_input_kind(self, _text: str) -> None:
        self.set_input_selection(GuiInputSelection.empty(self._current_input_kind()))

    def set_input_selection(self, selection: GuiInputSelection) -> None:
        """Set the current PDF input selection and refresh dependent controls."""
        self.selection_state = GuiPathSelectionState(
            input_selection=selection,
            output_directory=self.selection_state.output_directory,
        )
        self._refresh_path_state()

    def set_output_directory(self, directory: str) -> None:
        """Set the current output directory and refresh dependent controls."""
        self.selection_state = GuiPathSelectionState(
            input_selection=self.selection_state.input_selection,
            output_directory=directory,
        )
        self._refresh_path_state()

    def _refresh_path_state(self) -> None:
        self.pdf_input_field.setText(self.selection_state.input_selection.display_text())
        self.output_directory_field.setText(self.selection_state.output_directory)
        self._refresh_mode_controls()
        self._refresh_action_state()
        self._publish_status_message(self._status_message())

    def _status_message(self) -> str:
        has_input = self.selection_state.input_selection.is_valid
        has_output = bool(self.selection_state.output_directory)
        errors = validate_gui_settings(self.current_settings())
        if errors:
            return errors[0]
        if has_input and has_output:
            return "已选择 PDF 输入和产物目录"
        if has_input:
            return "已选择 PDF 输入，请选择产物目录"
        if has_output:
            return "已选择产物目录，请选择 PDF 输入"
        return "请选择 PDF 输入和产物目录"

    def _publish_status_message(self, message: str) -> None:
        window = self.window()
        status_bar = getattr(window, "statusBar", None)
        if callable(status_bar):
            status_bar().showMessage(message)

    def _current_input_kind(self) -> GuiInputKind:
        return input_kind_from_label(self.input_type_combo.currentText())

    def _current_conversion_mode(self) -> GuiConversionMode:
        return self._current_output_kind()

    def _current_output_kind(self) -> GuiOutputKind:
        if self.output_kind_combo.currentText() == "目录化项目":
            return GuiOutputKind.project
        return GuiOutputKind.tex_file

    def _set_conversion_mode(self, mode: GuiConversionMode) -> None:
        self.output_kind_combo.setCurrentText("目录化项目" if mode == GuiOutputKind.project else "单个 .tex")
        self._sync_gui_state()

    def _refresh_mode_controls(self) -> None:
        batch_input = self._current_input_kind() != GuiInputKind.single_file
        self.batch_workers_spin_box.setEnabled(batch_input)
        self.batch_pattern_field.setEnabled(self._current_input_kind() == GuiInputKind.directory)

        project_mode = self._current_output_kind() == GuiOutputKind.project
        self.structure_mode_combo.setEnabled(project_mode)
        self.structure_chunk_pages_spin_box.setEnabled(project_mode)
        self.structure_max_pages_spin_box.setEnabled(project_mode)

    def _sync_cache_controls(self) -> None:
        enabled = self.cache_enabled_checkbox.isChecked()
        self.cache_directory_field.setEnabled(enabled)
        self.cache_browse_button.setEnabled(enabled)
        if not enabled:
            self.clear_cache_checkbox.setChecked(False)
        self.clear_cache_checkbox.setEnabled(enabled)
        self._sync_gui_state()

    def _sync_image_controls(self) -> None:
        is_jpeg = self.image_format_combo.currentText() == "jpeg"
        self.jpeg_quality_spin_box.setEnabled(is_jpeg or self.image_format_combo.currentText() == "auto")
        self._sync_gui_state()

    def _sync_gui_state(self) -> None:
        self._refresh_action_state()
        self._publish_status_message(self._status_message())

    def _refresh_action_state(self) -> None:
        settings = self.current_settings()
        is_running = self._executor is not None
        self.add_task_button.setEnabled(
            not is_running and self.selection_state.can_add_task and not validate_gui_settings(settings)
        )
        self.start_button.setEnabled(
            not is_running
            and any(state.status == GuiTaskStatus.pending for state in self._task_states.values())
        )
        single_input = self._current_input_kind() == GuiInputKind.single_file
        self.manual_title_field.setEnabled(single_input and self.title_source_combo.currentText() != "llm")
        self.show_date_checkbox.setEnabled(True)
        self.beamer_title_page_checkbox.setEnabled(self.document_class_combo.currentText() in {"beamer", "ctexbeamer"})

        project_mode = self._current_output_kind() == GuiOutputKind.project
        self.structure_mode_combo.setEnabled(project_mode)
        self.structure_chunk_pages_spin_box.setEnabled(project_mode)
        self.structure_max_pages_spin_box.setEnabled(project_mode)
        self.batch_workers_spin_box.setEnabled(self._current_input_kind() != GuiInputKind.single_file)
        self.batch_pattern_field.setEnabled(self._current_input_kind() == GuiInputKind.directory)

    def current_settings(self) -> GuiConversionSettings:
        return GuiConversionSettings(
            path_state=self.selection_state,
            output_kind=self._current_output_kind(),
            confirm_overwrite=self.confirm_overwrite_checkbox.isChecked(),
            batch_pattern=self.batch_pattern_field.text(),
            pages=self.pages_field.text(),
            document_class=self.document_class_combo.currentText(),
            structure_mode=self.structure_mode_combo.currentText(),
            structure_chunk_pages=self.structure_chunk_pages_spin_box.value(),
            structure_max_pages=self.structure_max_pages_spin_box.value(),
            manual_title=self.manual_title_field.text(),
            title_source=self.title_source_combo.currentText(),
            show_date=self.show_date_checkbox.isChecked(),
            beamer_title_page=self.beamer_title_page_checkbox.isChecked(),
            model=self.model_field.text(),
            base_url=self.base_url_field.text(),
            api_key=self.api_key_field.text(),
            prompt_preset=self.prompt_preset_combo.currentText(),
            extra_prompt=self.extra_prompt_edit.toPlainText(),
            temperature=self.temperature_spin_box.value(),
            timeout_seconds=None if self.timeout_spin_box.value() == 0 else self.timeout_spin_box.value(),
            max_tokens=self.max_tokens_spin_box.value(),
            cache_enabled=self.cache_enabled_checkbox.isChecked(),
            cache_directory=self.cache_directory_field.text(),
            clear_cache=self.clear_cache_checkbox.isChecked(),
            chunk_pages=self.chunk_pages_spin_box.value(),
            prefetch_chunks=self.prefetch_chunks_spin_box.value(),
            llm_max_concurrency=self.llm_concurrency_spin_box.value(),
            llm_min_request_interval=self.llm_min_request_interval_spin_box.value(),
            batch_workers=self.batch_workers_spin_box.value(),
            image_dpi=self.image_dpi_spin_box.value(),
            image_dpi_min=self.image_dpi_min_spin_box.value(),
            image_dpi_max=None if self.image_dpi_max_spin_box.value() == 0 else self.image_dpi_max_spin_box.value(),
            image_format=self.image_format_combo.currentText(),
            jpeg_quality=self.jpeg_quality_spin_box.value(),
            llm_retries=self.llm_retries_spin_box.value(),
            llm_retry_initial_delay=self.llm_retry_initial_delay_spin_box.value(),
            llm_retry_max_delay=self.llm_retry_max_delay_spin_box.value(),
            beamer_box_style=self.beamer_box_style_combo.currentText(),
            ctex_font_profile=self.ctex_font_profile_combo.currentText(),
        )

    def set_settings(self, settings: GuiConversionSettings) -> None:
        self.selection_state = settings.path_state
        self.output_kind_combo.setCurrentText("目录化项目" if settings.output_kind == GuiOutputKind.project else "单个 .tex")
        self.confirm_overwrite_checkbox.setChecked(settings.confirm_overwrite)
        self.batch_pattern_field.setText(settings.batch_pattern)
        self.pages_field.setText(settings.pages)
        self.document_class_combo.setCurrentText(settings.document_class)
        self.structure_mode_combo.setCurrentText(settings.structure_mode)
        self.structure_chunk_pages_spin_box.setValue(settings.structure_chunk_pages)
        self.structure_max_pages_spin_box.setValue(settings.structure_max_pages)
        self.manual_title_field.setText(settings.manual_title)
        self.title_source_combo.setCurrentText(settings.title_source)
        self.show_date_checkbox.setChecked(settings.show_date)
        self.beamer_title_page_checkbox.setChecked(settings.beamer_title_page)
        self.model_field.setText(settings.model)
        self.base_url_field.setText(settings.base_url)
        self.api_key_field.setText(settings.api_key)
        self.prompt_preset_combo.setCurrentText(settings.prompt_preset)
        self.extra_prompt_edit.setPlainText(settings.extra_prompt)
        self.temperature_spin_box.setValue(settings.temperature)
        self.timeout_spin_box.setValue(0.0 if settings.timeout_seconds is None else settings.timeout_seconds)
        self.max_tokens_spin_box.setValue(settings.max_tokens)
        self.cache_enabled_checkbox.setChecked(settings.cache_enabled)
        self.cache_directory_field.setText(settings.cache_directory)
        self.clear_cache_checkbox.setChecked(settings.clear_cache)
        self.chunk_pages_spin_box.setValue(settings.chunk_pages)
        self.prefetch_chunks_spin_box.setValue(settings.prefetch_chunks)
        self.llm_concurrency_spin_box.setValue(settings.llm_max_concurrency)
        self.llm_min_request_interval_spin_box.setValue(settings.llm_min_request_interval)
        self.batch_workers_spin_box.setValue(settings.batch_workers)
        self.image_dpi_spin_box.setValue(settings.image_dpi)
        self.image_dpi_min_spin_box.setValue(settings.image_dpi_min)
        self.image_dpi_max_spin_box.setValue(0 if settings.image_dpi_max is None else settings.image_dpi_max)
        self.image_format_combo.setCurrentText(settings.image_format)
        self.jpeg_quality_spin_box.setValue(settings.jpeg_quality)
        self.llm_retries_spin_box.setValue(settings.llm_retries)
        self.llm_retry_initial_delay_spin_box.setValue(settings.llm_retry_initial_delay)
        self.llm_retry_max_delay_spin_box.setValue(settings.llm_retry_max_delay)
        self.beamer_box_style_combo.setCurrentText(settings.beamer_box_style)
        self.ctex_font_profile_combo.setCurrentText(settings.ctex_font_profile)
        self._sync_cache_controls()
        self._sync_image_controls()
        self._refresh_path_state()

    def reset_settings(self) -> None:
        self.set_settings(GuiConversionSettings())

    def validate_settings(self) -> list[str]:
        return validate_gui_settings(self.current_settings())

    def add_current_tasks(self) -> None:
        """Create pending in-memory tasks from current settings."""
        if self._executor is not None:
            self._publish_status_message("转换运行中，暂不能添加新任务。")
            return
        try:
            new_tasks = create_conversion_tasks(self.current_settings())
        except GuiTaskCreationError as exc:
            self._publish_status_message(str(exc))
            return
        self.tasks.extend(new_tasks)
        for task in new_tasks:
            self._task_states[task.task_id] = create_task_view_state(task)
        self._refresh_task_summary()
        self._publish_status_message(f"已添加 {len(new_tasks)} 个待处理任务")

    def start_pending_tasks(self) -> None:
        """Start background execution for all pending tasks."""
        if self._executor is not None:
            self._publish_status_message("转换正在运行。")
            return
        pending_tasks = [
            task
            for task in self.tasks
            if task.task_id in self._task_states
            and self._task_states[task.task_id].status == GuiTaskStatus.pending
        ]
        if not pending_tasks:
            self._publish_status_message("没有待处理任务。")
            self._refresh_action_state()
            return

        max_workers = self.current_settings().batch_workers
        executor = self._executor_factory(pending_tasks, max_workers=max_workers, parent=self)
        self._executor = executor
        executor.task_started.connect(self._handle_executor_task_started)
        executor.task_progress.connect(self._handle_executor_task_progress)
        executor.task_completed.connect(self._handle_executor_task_completed)
        executor.task_failed.connect(self._handle_executor_task_failed)
        executor.task_canceling.connect(self._handle_executor_task_canceling)
        executor.task_canceled.connect(self._handle_executor_task_canceled)
        executor.overwrite_confirmation_requested.connect(self._handle_overwrite_confirmation_requested)
        executor.all_finished.connect(self._handle_executor_finished)
        self._publish_status_message(f"开始执行 {len(pending_tasks)} 个任务")
        self._refresh_action_state()
        executor.start()

    def cancel_task(self, task_id: str) -> None:
        """Cancel one pending or running task."""
        state = self._task_states.get(task_id)
        if state is None:
            raise ValueError(f"未知任务：{task_id}")
        if state.status in TERMINAL_TASK_STATUSES:
            return
        if state.status == GuiTaskStatus.pending:
            if self._executor is not None:
                self._executor.cancel_task(task_id)
            mark_task_canceled(state)
            self._refresh_task_summary()
            self._publish_status_message("已取消待处理任务")
            return
        mark_task_canceling(state)
        if self._executor is not None:
            self._executor.cancel_task(task_id)
        self._refresh_task_summary()
        self._publish_status_message("正在取消任务")

    def task_view_states(self) -> tuple[GuiTaskViewState, ...]:
        """Return current task display states in queue order."""
        return tuple(
            self._task_states[task.task_id]
            for task in self.tasks
            if task.task_id in self._task_states
        )

    def update_task_state(self, task_id: str, update: GuiTaskRuntimeUpdate) -> None:
        """Apply a display update to one queued task."""
        state = self._task_states.get(task_id)
        if state is None:
            raise ValueError(f"未知任务：{task_id}")
        apply_task_update(state, update)
        self._refresh_task_summary()

    def handle_task_progress(self, task_id: str, event: ProgressEvent) -> None:
        """Merge one core progress event into one queued task."""
        state = self._task_states.get(task_id)
        if state is None:
            raise ValueError(f"未知任务：{task_id}")
        apply_progress_event(state, event)
        self._refresh_task_summary()

    def _handle_executor_task_started(self, task_id: str) -> None:
        state = self._task_states.get(task_id)
        if state is None or state.status == GuiTaskStatus.canceled:
            return
        mark_task_running(state)
        self._refresh_task_summary()
        self._publish_status_message(f"正在转换：{state.label}")

    def _handle_executor_task_progress(self, task_id: str, event: object) -> None:
        if isinstance(event, ProgressEvent):
            self.handle_task_progress(task_id, event)

    def _handle_executor_task_completed(self, task_id: str, result: str, notes: object) -> None:
        state = self._task_states.get(task_id)
        if state is None:
            return
        resolved_notes = tuple(notes) if isinstance(notes, tuple) else ()
        mark_task_completed(state, result=result, notes=resolved_notes)
        self._refresh_task_summary()
        self._publish_status_message(f"转换完成：{state.label}")

    def _handle_executor_task_failed(self, task_id: str, error: str) -> None:
        state = self._task_states.get(task_id)
        if state is None:
            return
        mark_task_failed(state, error)
        self._refresh_task_summary()
        self._publish_status_message(f"转换失败：{state.label}")

    def _handle_executor_task_canceling(self, task_id: str) -> None:
        state = self._task_states.get(task_id)
        if state is None:
            return
        mark_task_canceling(state)
        self._refresh_task_summary()

    def _handle_executor_task_canceled(self, task_id: str) -> None:
        state = self._task_states.get(task_id)
        if state is None:
            return
        mark_task_canceled(state)
        self._refresh_task_summary()
        self._publish_status_message(f"已取消：{state.label}")

    def _handle_overwrite_confirmation_requested(self, request: object) -> None:
        if not isinstance(request, GuiOverwriteConfirmationRequest):
            return
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("确认覆盖")
        task_label = request.task_label or request.task_id or "当前任务"
        message.setText(f"{request.summary}：{task_label}")
        message.setInformativeText(f"{request.details}\n\n目标：{request.target}")
        message.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        message.setDefaultButton(QMessageBox.StandardButton.No)
        message.button(QMessageBox.StandardButton.Yes).setText("覆盖")
        message.button(QMessageBox.StandardButton.No).setText("取消")
        approved = message.exec() == QMessageBox.StandardButton.Yes
        request.resolve(approved)

    def _handle_executor_finished(self) -> None:
        if self._executor is not None:
            self._executor.deleteLater()
            self._executor = None
        self._refresh_task_summary()
        self._publish_status_message("后台转换已结束")

    def _refresh_task_summary(self) -> None:
        counts = {status: 0 for status in GuiTaskStatus}
        states = list(self.task_view_states())
        for state in states:
            counts[state.status] += 1
        for status, label in self.task_metric_labels.items():
            label.setText(str(counts[status]))
        empty_status = self.findChild(QLabel, "taskEmptyStatusLabel")
        if empty_status is not None:
            total = len(states)
            empty_status.setText("队列空闲" if total == 0 else f"已创建 {total} 个任务")
        self._refresh_task_rows(states)
        self._refresh_overall_progress(states)
        self._refresh_action_state()

    def _refresh_task_rows(self, states: list[GuiTaskViewState]) -> None:
        active_ids = {state.task_id for state in states}
        for task_id, row in list(self._task_rows.items()):
            if task_id not in active_ids:
                self.task_rows_layout.removeWidget(row)
                row.deleteLater()
                del self._task_rows[task_id]

        for state in states:
            row = self._task_rows.get(state.task_id)
            if row is None:
                row = self._create_task_row(state)
                self._task_rows[state.task_id] = row
                self.task_rows_layout.addWidget(row)
            self._update_task_row(row, state)

        has_tasks = bool(states)
        self.task_empty_state.setVisible(not has_tasks)
        self.task_list_scroll_area.setVisible(has_tasks)

    def _create_task_row(self, state: GuiTaskViewState) -> QFrame:
        row = QFrame(self.task_rows_container)
        row.setObjectName(f"taskRow_{state.task_id}")
        row.setProperty("taskRow", True)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        title = QLabel(state.label, row)
        title.setObjectName(f"taskTitleLabel_{state.task_id}")
        title.setProperty("sectionTitle", True)
        title.setWordWrap(True)
        header.addWidget(title, 1)

        status = QLabel(row)
        status.setObjectName(f"taskStatusBadge_{state.task_id}")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setProperty("taskStatus", state.status.value)
        header.addWidget(status)

        cancel = self._make_icon_button(
            f"taskCancelButton_{state.task_id}",
            QStyle.StandardPixmap.SP_DialogCancelButton,
            "取消任务",
        )
        cancel.clicked.connect(lambda _checked=False, task_id=state.task_id: self.cancel_task(task_id))
        header.addWidget(cancel)
        layout.addLayout(header)

        target = QLabel(row)
        target.setObjectName(f"taskTargetLabel_{state.task_id}")
        target.setProperty("muted", True)
        target.setWordWrap(True)
        layout.addWidget(target)

        stage = QLabel(row)
        stage.setObjectName(f"taskStageLabel_{state.task_id}")
        stage.setProperty("muted", True)
        stage.setWordWrap(True)
        layout.addWidget(stage)

        progress = QProgressBar(row)
        progress.setObjectName(f"taskProgressBar_{state.task_id}")
        progress.setRange(0, 100)
        progress.setTextVisible(True)
        layout.addWidget(progress)

        metrics = QHBoxLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setSpacing(10)
        cache = QLabel(row)
        cache.setObjectName(f"taskCacheLabel_{state.task_id}")
        cache.setProperty("muted", True)
        metrics.addWidget(cache)
        retry = QLabel(row)
        retry.setObjectName(f"taskRetryLabel_{state.task_id}")
        retry.setProperty("muted", True)
        metrics.addWidget(retry)
        metrics.addStretch(1)
        layout.addLayout(metrics)

        result = QLabel(row)
        result.setObjectName(f"taskResultLabel_{state.task_id}")
        result.setProperty("muted", True)
        result.setWordWrap(True)
        layout.addWidget(result)

        return row

    def _update_task_row(self, row: QFrame, state: GuiTaskViewState) -> None:
        status = row.findChild(QLabel, f"taskStatusBadge_{state.task_id}")
        if status is not None:
            status.setText(state.status_label)
            status.setProperty("taskStatus", state.status.value)
            status.style().unpolish(status)
            status.style().polish(status)

        cancel = row.findChild(QToolButton, f"taskCancelButton_{state.task_id}")
        if cancel is not None:
            active = state.status not in TERMINAL_TASK_STATUSES
            cancel.setEnabled(active)
            cancel.setVisible(active)

        target = row.findChild(QLabel, f"taskTargetLabel_{state.task_id}")
        if target is not None:
            target.setText(self._task_target_text(state))

        stage = row.findChild(QLabel, f"taskStageLabel_{state.task_id}")
        if stage is not None:
            detail = f"阶段：{state.stage_label}"
            if state.recent_event:
                detail = f"{detail} · {state.recent_event}"
            stage.setText(detail)

        progress = row.findChild(QProgressBar, f"taskProgressBar_{state.task_id}")
        if progress is not None:
            progress.setValue(state.progress)
            progress.setFormat(f"{state.progress}%")

        cache = row.findChild(QLabel, f"taskCacheLabel_{state.task_id}")
        if cache is not None:
            cache.setText(f"缓存命中 {state.cache_hits}")

        retry = row.findChild(QLabel, f"taskRetryLabel_{state.task_id}")
        if retry is not None:
            retry.setText(f"重试 {state.retries}")

        result = row.findChild(QLabel, f"taskResultLabel_{state.task_id}")
        if result is not None:
            result.setText(self._task_result_text(state))

    def _refresh_overall_progress(self, states: list[GuiTaskViewState]) -> None:
        if not states:
            self.overall_progress_bar.setValue(0)
            return
        average = round(sum(state.progress for state in states) / len(states))
        self.overall_progress_bar.setValue(max(0, min(100, average)))

    def _task_target_text(self, state: GuiTaskViewState) -> str:
        kind = "目录化项目" if state.task.output_target.kind == GuiOutputKind.project else "LaTeX 文件"
        return f"{kind}：{state.task.output_target.path}"

    def _task_result_text(self, state: GuiTaskViewState) -> str:
        if state.status == GuiTaskStatus.failed:
            return f"失败原因：{state.error or '未知错误'}"
        if state.status == GuiTaskStatus.canceled:
            return "任务已取消"
        if state.status == GuiTaskStatus.completed:
            return f"完成结果：{state.result or state.task.output_target.path}"
        if state.notes:
            return "；".join(state.notes)
        return "等待后台执行"

    def close_executor(self) -> None:
        """Request executor shutdown when the owning window is closing."""
        if self._executor is not None:
            self._executor.shutdown()
            self._executor.deleteLater()
            self._executor = None
