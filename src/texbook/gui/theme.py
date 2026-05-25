"""Fluent-style visual tokens for the TexBook GUI."""

from __future__ import annotations


def build_fluent_stylesheet() -> str:
    """Return the light Fluent-style stylesheet used by the GUI shell."""
    return """
    QWidget#conversionMainPanel {
        background: #f6f7f9;
        color: #1f2328;
        font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
        font-size: 13px;
    }

    QFrame#topCommandBar {
        background: #ffffff;
        border: 1px solid #e4e7ec;
        border-radius: 8px;
    }

    QFrame[panel="true"] {
        background: #ffffff;
        border: 1px solid #e4e7ec;
        border-radius: 8px;
    }

    QFrame#taskEmptyState {
        background: #f8fafc;
        border: 1px dashed #cfd6df;
        border-radius: 8px;
    }

    QFrame#queueMetric {
        background: #f8fafc;
        border: 1px solid #e4e7ec;
        border-radius: 6px;
    }

    QLabel#appTitleLabel {
        color: #111827;
        font-size: 20px;
        font-weight: 700;
    }

    QLabel#appSubtitleLabel,
    QLabel[muted="true"] {
        color: #687385;
    }

    QLabel[sectionTitle="true"] {
        color: #111827;
        font-size: 15px;
        font-weight: 700;
    }

    QLabel[rowLabel="true"] {
        color: #344054;
        font-weight: 600;
    }

    QLineEdit,
    QTextEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox {
        background: #fbfcfe;
        border: 1px solid #d7dde5;
        border-radius: 6px;
        padding: 6px 9px;
        min-height: 24px;
        selection-background-color: #0f6cbd;
    }

    QTextEdit {
        min-height: 60px;
    }

    QLineEdit:focus,
    QTextEdit:focus,
    QComboBox:focus,
    QSpinBox:focus,
    QDoubleSpinBox:focus {
        background: #ffffff;
        border: 1px solid #0f6cbd;
    }

    QComboBox::drop-down {
        border: none;
        width: 24px;
    }

    QPushButton,
    QToolButton {
        background: #ffffff;
        border: 1px solid #d7dde5;
        border-radius: 6px;
        color: #1f2328;
        padding: 6px 10px;
        min-height: 26px;
    }

    QPushButton:hover,
    QToolButton:hover {
        background: #f3f6fa;
        border-color: #c8d0da;
    }

    QPushButton:pressed,
    QToolButton:pressed {
        background: #e9eef5;
    }

    QPushButton:disabled,
    QToolButton:disabled,
    QLineEdit:disabled,
    QTextEdit:disabled,
    QComboBox:disabled,
    QSpinBox:disabled,
    QDoubleSpinBox:disabled {
        background: #f3f4f6;
        color: #98a2b3;
        border-color: #e1e5ea;
    }

    QPushButton#startButton,
    QPushButton#addTaskButton {
        background: #0f6cbd;
        border: 1px solid #0f6cbd;
        color: #ffffff;
        font-weight: 700;
    }

    QPushButton#startButton:hover,
    QPushButton#addTaskButton:hover {
        background: #115ea3;
        border-color: #115ea3;
    }

    QPushButton#startButton:disabled,
    QPushButton#addTaskButton:disabled {
        background: #d7e5f7;
        border-color: #d7e5f7;
        color: #7694b6;
    }

    QRadioButton,
    QCheckBox {
        spacing: 7px;
        color: #344054;
    }

    QRadioButton::indicator,
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
    }

    QProgressBar {
        background: #eef2f7;
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
    }

    QProgressBar::chunk {
        background: #0f6cbd;
        border-radius: 4px;
    }

    QScrollArea,
    QWidget#settingsPane,
    QWidget#taskListBody {
        background: transparent;
        border: none;
    }
    """
