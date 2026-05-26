"""Fluent-style visual tokens for the TexBook GUI."""

from __future__ import annotations

from texbook.gui.display import DEFAULT_GUI_FONT_FAMILY, GuiThemeMode, coerce_font_point_size


_LIGHT_TOKENS = {
    "window_bg": "#f6f7f9",
    "surface": "#ffffff",
    "surface_soft": "#f8fafc",
    "row_bg": "#fbfcfe",
    "border": "#e4e7ec",
    "border_strong": "#d7dde5",
    "border_soft": "#cfd6df",
    "text": "#1f2328",
    "text_strong": "#111827",
    "muted": "#687385",
    "row_label": "#344054",
    "accent": "#0f6cbd",
    "accent_hover": "#115ea3",
    "accent_disabled_bg": "#d7e5f7",
    "accent_disabled_text": "#7694b6",
    "hover": "#f3f6fa",
    "pressed": "#e9eef5",
    "disabled_bg": "#f3f4f6",
    "disabled_text": "#98a2b3",
    "disabled_border": "#e1e5ea",
    "progress_bg": "#eef2f7",
    "menu_selected": "#eef6ff",
    "pending_bg": "#eef2f7",
    "pending_text": "#475467",
    "running_bg": "#dbeafe",
    "running_text": "#1d4ed8",
    "canceling_bg": "#fef3c7",
    "canceling_text": "#92400e",
    "canceled_bg": "#f3f4f6",
    "canceled_text": "#4b5563",
    "completed_bg": "#dcfce7",
    "completed_text": "#166534",
    "failed_bg": "#fee2e2",
    "failed_text": "#b42318",
}

_DARK_TOKENS = {
    "window_bg": "#17191d",
    "surface": "#24272d",
    "surface_soft": "#1f2228",
    "row_bg": "#20242b",
    "border": "#343944",
    "border_strong": "#4a515f",
    "border_soft": "#4f5868",
    "text": "#edf1f7",
    "text_strong": "#ffffff",
    "muted": "#a8b0be",
    "row_label": "#d6dbe5",
    "accent": "#4aa3ff",
    "accent_hover": "#67b4ff",
    "accent_disabled_bg": "#213952",
    "accent_disabled_text": "#86a8ca",
    "hover": "#2d333d",
    "pressed": "#363d49",
    "disabled_bg": "#202329",
    "disabled_text": "#727b89",
    "disabled_border": "#303640",
    "progress_bg": "#2b3039",
    "menu_selected": "#26384b",
    "pending_bg": "#303640",
    "pending_text": "#d7dde8",
    "running_bg": "#17385f",
    "running_text": "#9dccff",
    "canceling_bg": "#4b3711",
    "canceling_text": "#ffd78a",
    "canceled_bg": "#30333a",
    "canceled_text": "#c8ced8",
    "completed_bg": "#183d2a",
    "completed_text": "#8ee2a9",
    "failed_bg": "#4a1f23",
    "failed_text": "#ffabb0",
}


def build_fluent_stylesheet(
    theme: GuiThemeMode | str = GuiThemeMode.light,
    *,
    font_point_size: int = 11,
) -> str:
    """Return the Fluent-style stylesheet used by the GUI shell."""
    try:
        theme_mode = GuiThemeMode(theme)
    except ValueError:
        theme_mode = GuiThemeMode.light
    token = _DARK_TOKENS if theme_mode == GuiThemeMode.dark else _LIGHT_TOKENS
    base_point_size = coerce_font_point_size(font_point_size)
    title_point_size = base_point_size + 6
    section_point_size = base_point_size + 1
    field_min_height = max(28, base_point_size * 2 + 6)
    button_min_height = max(30, base_point_size * 2 + 8)

    return f"""
    QMainWindow,
    QWidget#conversionMainPanel {{
        background: {token["window_bg"]};
        color: {token["text"]};
        font-family: "{DEFAULT_GUI_FONT_FAMILY}", "Segoe UI", sans-serif;
        font-size: {base_point_size}pt;
    }}

    QMenuBar,
    QStatusBar {{
        background: {token["surface"]};
        color: {token["text"]};
        border: none;
    }}

    QMenuBar {{
        border-bottom: 1px solid {token["border"]};
    }}

    QMenuBar::item:selected,
    QMenu::item:selected {{
        background: {token["menu_selected"]};
    }}

    QMenu {{
        background: {token["surface"]};
        color: {token["text"]};
        border: 1px solid {token["border"]};
    }}

    QDialog {{
        background: {token["surface"]};
        color: {token["text"]};
    }}

    QDialog#aboutDialog,
    QDialog#settingsDialog {{
        background: {token["surface"]};
        color: {token["text"]};
    }}

    QDialog QLabel,
    QMessageBox QLabel {{
        background: transparent;
        color: {token["text"]};
    }}

    QDialog QLabel[muted="true"],
    QMessageBox QLabel[muted="true"] {{
        color: {token["muted"]};
    }}

    QDialog QPushButton,
    QDialog QToolButton,
    QMessageBox QPushButton {{
        background: {token["surface"]};
        color: {token["text"]};
    }}

    QMessageBox {{
        background: {token["surface"]};
        color: {token["text"]};
    }}

    QFrame#topCommandBar {{
        background: {token["surface"]};
        border: 1px solid {token["border"]};
        border-radius: 8px;
    }}

    QFrame[panel="true"] {{
        background: {token["surface"]};
        border: 1px solid {token["border"]};
        border-radius: 8px;
    }}

    QFrame#taskEmptyState {{
        background: {token["surface_soft"]};
        border: 1px dashed {token["border_soft"]};
        border-radius: 8px;
    }}

    QFrame#queueMetric {{
        background: {token["surface_soft"]};
        border: 1px solid {token["border"]};
        border-radius: 6px;
    }}

    QFrame[taskRow="true"] {{
        background: {token["row_bg"]};
        border: 1px solid {token["border"]};
        border-radius: 8px;
    }}

    QLabel#appTitleLabel {{
        color: {token["text_strong"]};
        font-size: {title_point_size}pt;
        font-weight: 700;
    }}

    QLabel#appSubtitleLabel,
    QLabel[muted="true"] {{
        color: {token["muted"]};
    }}

    QLabel[sectionTitle="true"] {{
        color: {token["text_strong"]};
        font-size: {section_point_size}pt;
        font-weight: 700;
    }}

    QLabel[rowLabel="true"] {{
        color: {token["row_label"]};
        font-weight: 600;
    }}

    QLabel[taskStatus="pending"] {{
        background: {token["pending_bg"]};
        color: {token["pending_text"]};
        border-radius: 6px;
        padding: 4px 9px;
        font-weight: 700;
    }}

    QLabel[taskStatus="running"] {{
        background: {token["running_bg"]};
        color: {token["running_text"]};
        border-radius: 6px;
        padding: 4px 9px;
        font-weight: 700;
    }}

    QLabel[taskStatus="canceling"] {{
        background: {token["canceling_bg"]};
        color: {token["canceling_text"]};
        border-radius: 6px;
        padding: 4px 9px;
        font-weight: 700;
    }}

    QLabel[taskStatus="canceled"] {{
        background: {token["canceled_bg"]};
        color: {token["canceled_text"]};
        border-radius: 6px;
        padding: 4px 9px;
        font-weight: 700;
    }}

    QLabel[taskStatus="completed"] {{
        background: {token["completed_bg"]};
        color: {token["completed_text"]};
        border-radius: 6px;
        padding: 4px 9px;
        font-weight: 700;
    }}

    QLabel[taskStatus="failed"] {{
        background: {token["failed_bg"]};
        color: {token["failed_text"]};
        border-radius: 6px;
        padding: 4px 9px;
        font-weight: 700;
    }}

    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox {{
        background: {token["row_bg"]};
        border: 1px solid {token["border_strong"]};
        border-radius: 6px;
        color: {token["text"]};
        padding: 7px 10px;
        min-height: {field_min_height}px;
        selection-background-color: {token["accent"]};
    }}

    QTextEdit {{
        min-height: 72px;
    }}

    QLineEdit:focus,
    QTextEdit:focus,
    QSpinBox:focus,
    QDoubleSpinBox:focus {{
        background: {token["surface"]};
        border: 1px solid {token["accent"]};
    }}

    QPushButton,
    QToolButton {{
        background: {token["surface"]};
        border: 1px solid {token["border_strong"]};
        border-radius: 6px;
        color: {token["text"]};
        padding: 7px 11px;
        min-height: {button_min_height}px;
    }}

    QPushButton:hover,
    QToolButton:hover {{
        background: {token["hover"]};
        border-color: {token["border_soft"]};
    }}

    QPushButton:pressed,
    QToolButton:pressed {{
        background: {token["pressed"]};
    }}

    QPushButton:disabled,
    QToolButton:disabled,
    QLineEdit:disabled,
    QTextEdit:disabled,
    QSpinBox:disabled,
    QDoubleSpinBox:disabled {{
        background: {token["disabled_bg"]};
        color: {token["disabled_text"]};
        border-color: {token["disabled_border"]};
    }}

    QPushButton#startButton,
    QPushButton#addTaskButton {{
        background: {token["accent"]};
        border: 1px solid {token["accent"]};
        color: #ffffff;
        font-weight: 700;
    }}

    QPushButton#startButton:hover,
    QPushButton#addTaskButton:hover {{
        background: {token["accent_hover"]};
        border-color: {token["accent_hover"]};
    }}

    QPushButton#startButton:disabled,
    QPushButton#addTaskButton:disabled {{
        background: {token["accent_disabled_bg"]};
        border-color: {token["accent_disabled_bg"]};
        color: {token["accent_disabled_text"]};
    }}

    QRadioButton,
    QCheckBox {{
        spacing: 7px;
        color: {token["row_label"]};
    }}

    QWidget[choiceGroup="true"]:disabled QCheckBox {{
        color: {token["disabled_text"]};
    }}

    QRadioButton::indicator,
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
    }}

    QProgressBar {{
        background: {token["progress_bg"]};
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
        color: {token["text"]};
    }}

    QProgressBar::chunk {{
        background: {token["accent"]};
        border-radius: 4px;
    }}

    QScrollArea,
        QWidget#settingsPane,
        QWidget#taskListBody {{
        background: transparent;
        border: none;
    }}
    """
