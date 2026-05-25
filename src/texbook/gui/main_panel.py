"""Main conversion panel for the TexBook GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from texbook.gui.resources import APP_DISPLAY_NAME
from texbook.gui.selection import (
    GuiInputKind,
    GuiInputSelection,
    GuiPathSelectionState,
    input_kind_from_label,
)
from texbook.gui.widgets import InlineField, MetricPill, OptionGrid, SectionPanel


class ConversionMainPanel(QWidget):
    """Fluent Design main panel shown when the GUI opens."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("conversionMainPanel")
        self.selection_state = GuiPathSelectionState()

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
        start.setToolTip("任务执行流程将在后续阶段接入。")
        start.setEnabled(False)
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
        layout.addWidget(self._create_mode_panel())

        parameters = QWidget(pane)
        parameters.setObjectName("parametersPanel")
        parameters_layout = QVBoxLayout(parameters)
        parameters_layout.setContentsMargins(0, 0, 0, 0)
        parameters_layout.setSpacing(12)
        parameters_layout.addWidget(self._create_page_document_panel())
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

        panel.body_layout.addWidget(grid)
        return panel

    def _create_output_panel(self) -> SectionPanel:
        panel = SectionPanel("输出", object_name="outputPanel", parent=self)
        grid = OptionGrid(parent=panel)

        output_dir = QLineEdit(panel)
        output_dir.setObjectName("outputDirectoryField")
        output_dir.setPlaceholderText("选择产物目录")
        output_dir.setReadOnly(True)
        self.output_directory_field = output_dir
        browse = self._make_icon_button(
            "outputBrowseButton",
            QStyle.StandardPixmap.SP_DirOpenIcon,
            "浏览产物目录",
        )
        self.output_browse_button = browse
        grid.add_row("产物目录", InlineField(output_dir, browse, parent=panel))

        overwrite = QCheckBox("覆盖前确认", panel)
        overwrite.setObjectName("confirmOverwriteCheckBox")
        overwrite.setChecked(True)
        grid.add_row("写盘策略", overwrite)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_mode_panel(self) -> SectionPanel:
        panel = SectionPanel("转换模式", object_name="modePanel", parent=self)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._mode_group = QButtonGroup(panel)
        for index, (name, text) in enumerate(
            [
                ("singleFileModeRadio", "单文件 .tex"),
                ("projectModeRadio", "目录化项目"),
                ("batchModeRadio", "批量任务"),
            ]
        ):
            radio = QRadioButton(text, panel)
            radio.setObjectName(name)
            radio.setChecked(index == 0)
            self._mode_group.addButton(radio, index)
            layout.addWidget(radio)

        layout.addStretch(1)
        panel.body_layout.addLayout(layout)
        return panel

    def _create_page_document_panel(self) -> SectionPanel:
        panel = SectionPanel("页面与文档类", object_name="documentOptionsPanel", parent=self)
        grid = OptionGrid(parent=panel)

        pages = QLineEdit(panel)
        pages.setObjectName("pagesField")
        pages.setPlaceholderText("全部页面")
        grid.add_row("页面范围", pages)

        document_class = QComboBox(panel)
        document_class.setObjectName("documentClassCombo")
        document_class.addItems(
            ["auto", "ctexart", "ctexbook", "ctexbeamer", "article", "book", "beamer"]
        )
        grid.add_row("文档类", document_class)

        structure = QComboBox(panel)
        structure.setObjectName("structureModeCombo")
        structure.addItems(["auto", "off", "local", "llm"])
        grid.add_row("结构规划", structure)

        title_page = QCheckBox("生成 Beamer 标题页", panel)
        title_page.setObjectName("beamerTitlePageCheckBox")
        title_page.setChecked(True)
        grid.add_row("标题页", title_page)

        show_date = QCheckBox("显示日期", panel)
        show_date.setObjectName("showDateCheckBox")
        grid.add_row("日期", show_date)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_model_panel(self) -> SectionPanel:
        panel = SectionPanel("模型配置", object_name="modelOptionsPanel", parent=self)
        grid = OptionGrid(parent=panel)

        model = QLineEdit(panel)
        model.setObjectName("modelField")
        model.setPlaceholderText("TEXBOOK_MODEL")
        grid.add_row("模型", model)

        base_url = QLineEdit(panel)
        base_url.setObjectName("baseUrlField")
        base_url.setPlaceholderText("TEXBOOK_BASE_URL")
        grid.add_row("Base URL", base_url)

        api_key = QLineEdit(panel)
        api_key.setObjectName("apiKeyField")
        api_key.setEchoMode(QLineEdit.EchoMode.Password)
        api_key.setPlaceholderText("TEXBOOK_API_KEY")
        grid.add_row("API Key", api_key)

        title_source = QComboBox(panel)
        title_source.setObjectName("titleSourceCombo")
        title_source.addItems(["filename", "llm"])
        grid.add_row("标题来源", title_source)

        preset = QComboBox(panel)
        preset.setObjectName("promptPresetCombo")
        preset.addItem("chinese-math")
        grid.add_row("Prompt 预设", preset)

        extra_prompt = QTextEdit(panel)
        extra_prompt.setObjectName("extraPromptEdit")
        extra_prompt.setPlaceholderText("追加一次性转换要求")
        grid.add_row("额外要求", extra_prompt)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_cache_panel(self) -> SectionPanel:
        panel = SectionPanel("缓存与并发", object_name="cacheConcurrencyPanel", parent=self)
        grid = OptionGrid(parent=panel)

        cache_enabled = QCheckBox("启用缓存", panel)
        cache_enabled.setObjectName("cacheEnabledCheckBox")
        cache_enabled.setChecked(True)
        grid.add_row("缓存", cache_enabled)

        cache_dir = QLineEdit(panel)
        cache_dir.setObjectName("cacheDirectoryField")
        cache_dir.setPlaceholderText("build/.texbook_cache")
        browse = self._make_icon_button(
            "cacheBrowseButton",
            QStyle.StandardPixmap.SP_DirOpenIcon,
            "浏览缓存目录",
        )
        browse.setEnabled(False)
        grid.add_row("缓存目录", InlineField(cache_dir, browse, parent=panel))

        chunk_pages = self._make_spin_box("chunkPagesSpinBox", 1, 64, 4)
        grid.add_row("Chunk 页数", chunk_pages)

        prefetch = self._make_spin_box("prefetchChunksSpinBox", 0, 16, 1)
        grid.add_row("预渲染", prefetch)

        llm_concurrency = self._make_spin_box("llmConcurrencySpinBox", 1, 16, 1)
        grid.add_row("LLM 并发", llm_concurrency)

        batch_workers = self._make_spin_box("batchWorkersSpinBox", 1, 16, 1)
        grid.add_row("批量 Worker", batch_workers)

        panel.body_layout.addWidget(grid)
        return panel

    def _create_advanced_panel(self) -> SectionPanel:
        panel = SectionPanel("高级参数", object_name="advancedOptionsPanel", parent=self)
        grid = OptionGrid(parent=panel)

        image_dpi = self._make_spin_box("imageDpiSpinBox", 72, 600, 160)
        grid.add_row("图像 DPI", image_dpi)

        image_format = QComboBox(panel)
        image_format.setObjectName("imageFormatCombo")
        image_format.addItems(["auto", "png", "jpeg"])
        grid.add_row("图像格式", image_format)

        retries = self._make_spin_box("llmRetriesSpinBox", 0, 10, 2)
        grid.add_row("重试次数", retries)

        interval = QDoubleSpinBox(panel)
        interval.setObjectName("llmIntervalSpinBox")
        interval.setRange(0.0, 600.0)
        interval.setDecimals(1)
        interval.setSingleStep(0.5)
        interval.setValue(0.0)
        interval.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        grid.add_row("请求间隔", interval)

        temperature = QDoubleSpinBox(panel)
        temperature.setObjectName("temperatureSpinBox")
        temperature.setRange(0.0, 2.0)
        temperature.setDecimals(2)
        temperature.setSingleStep(0.05)
        temperature.setValue(1.0)
        grid.add_row("Temperature", temperature)

        max_tokens = self._make_spin_box("maxTokensSpinBox", 1, 512000, 128000)
        grid.add_row("Max tokens", max_tokens)

        beamer_style = QComboBox(panel)
        beamer_style.setObjectName("beamerBoxStyleCombo")
        beamer_style.addItems(["block", "tcolorbox"])
        grid.add_row("Beamer 块", beamer_style)

        ctex_font = QComboBox(panel)
        ctex_font.setObjectName("ctexFontProfileCombo")
        ctex_font.addItems(["default", "local"])
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
        for index, (label, value) in enumerate(
            [("待处理", "0"), ("运行中", "0"), ("完成", "0"), ("失败", "0")]
        ):
            metrics.addWidget(MetricPill(label, value, parent=panel), index // 2, index % 2)
        panel.body_layout.addLayout(metrics)

        body = QWidget(panel)
        body.setObjectName("taskListBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

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

        body_layout.addWidget(empty)

        progress = QProgressBar(body)
        progress.setObjectName("overallProgressBar")
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(False)
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
        self.input_type_combo.currentTextChanged.connect(self._change_input_kind)

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
        directory = QFileDialog.getExistingDirectory(self, "选择产物目录", "")
        if directory:
            self.set_output_directory(directory)

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
        self.add_task_button.setEnabled(self.selection_state.can_add_task)
        self._publish_status_message(self._path_status_message())

    def _path_status_message(self) -> str:
        has_input = self.selection_state.input_selection.is_valid
        has_output = bool(self.selection_state.output_directory)
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
