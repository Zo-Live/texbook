"""Reusable widgets for the TexBook GUI interface layer."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SectionPanel(QFrame):
    """A compact Fluent-style panel with a title and content area."""

    def __init__(
        self,
        title: str,
        *,
        subtitle: str = "",
        object_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if object_name:
            self.setObjectName(object_name)
        self.setProperty("panel", True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(3)

        title_label = QLabel(title, self)
        title_label.setProperty("sectionTitle", True)
        header.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle, self)
            subtitle_label.setProperty("muted", True)
            subtitle_label.setWordWrap(True)
            header.addWidget(subtitle_label)

        layout.addLayout(header)

        self.body = QWidget(self)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(10)
        layout.addWidget(self.body)


class OptionGrid(QWidget):
    """Two-column form grid for dense conversion options."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setHorizontalSpacing(12)
        self.layout.setVerticalSpacing(10)
        self.layout.setColumnStretch(0, 0)
        self.layout.setColumnStretch(1, 1)
        self._row = 0

    def add_row(self, label: str, control: QWidget) -> None:
        label_widget = QLabel(label, self)
        label_widget.setProperty("rowLabel", True)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(label_widget, self._row, 0)
        self.layout.addWidget(control, self._row, 1)
        self._row += 1


class InlineField(QWidget):
    """A field paired with a compact trailing button."""

    def __init__(self, field: QWidget, button: QWidget, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(field, 1)
        layout.addWidget(button)


class MetricPill(QFrame):
    """Small queue metric block used by the task list panel."""

    def __init__(self, label: str, value: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("queueMetric")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        value_label = QLabel(value, self)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setProperty("sectionTitle", True)
        layout.addWidget(value_label)

        label_widget = QLabel(label, self)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_widget.setProperty("muted", True)
        layout.addWidget(label_widget)
