"""Reusable widgets for the TexBook GUI interface layer."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
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

        self.title_label = QLabel(title, self)
        self.title_label.setProperty("sectionTitle", True)
        header.addWidget(self.title_label)

        self.subtitle_label: QLabel | None = None
        if subtitle:
            self.subtitle_label = QLabel(subtitle, self)
            self.subtitle_label.setProperty("muted", True)
            self.subtitle_label.setWordWrap(True)
            header.addWidget(self.subtitle_label)

        layout.addLayout(header)

        self.body = QWidget(self)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(10)
        layout.addWidget(self.body)

    def set_title(self, title: str) -> None:
        """Update the visible section title."""
        self.title_label.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        """Update the visible section subtitle."""
        if self.subtitle_label is not None:
            self.subtitle_label.setText(subtitle)


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

    def add_row(self, label: str, control: QWidget) -> QLabel:
        label_widget = QLabel(label, self)
        label_widget.setProperty("rowLabel", True)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(label_widget, self._row, 0)
        self.layout.addWidget(control, self._row, 1)
        self._row += 1
        return label_widget


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

        self.value_label = QLabel(value, self)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setProperty("sectionTitle", True)
        layout.addWidget(self.value_label)

        self.label_widget = QLabel(label, self)
        self.label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_widget.setProperty("muted", True)
        layout.addWidget(self.label_widget)

    def set_label(self, label: str) -> None:
        """Update the metric label."""
        self.label_widget.setText(label)


class ChoiceGrid(QWidget):
    """Exclusive check-box option group with at most three options per row."""

    value_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("choiceGroup", True)
        self._value_by_button: dict[QCheckBox, str] = {}
        self._button_by_value: dict[str, QCheckBox] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.buttonToggled.connect(self._handle_button_toggled)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(12)
        self._layout.setVerticalSpacing(8)

    def set_items(
        self,
        items: tuple[tuple[str, str], ...],
        *,
        current_value: str | None = None,
    ) -> None:
        """Replace option labels while preserving the selected stable value."""
        selected = current_value if current_value is not None else self.value()
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._group.removeButton(widget)
                widget.deleteLater()
        self._value_by_button.clear()
        self._button_by_value.clear()

        for index, (value, label) in enumerate(items):
            option = QCheckBox(label, self)
            option.setProperty("choiceOption", True)
            option.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            self._group.addButton(option)
            self._value_by_button[option] = value
            self._button_by_value[value] = option
            self._layout.addWidget(option, index // 3, index % 3)

        self.set_value(selected if selected in self._button_by_value else "")

    def value(self) -> str:
        """Return the stable value for the checked option."""
        checked = self._group.checkedButton()
        if not isinstance(checked, QCheckBox):
            return ""
        return self._value_by_button.get(checked, "")

    def set_value(self, value: str, *, emit: bool = True) -> None:
        """Select an option by stable value."""
        button = self._button_by_value.get(value)
        if button is None:
            button = next(iter(self._button_by_value.values()), None)
        if button is None:
            return
        old_value = self.value()
        previous = self._group.blockSignals(True)
        button.setChecked(True)
        self._group.blockSignals(previous)
        new_value = self.value()
        if emit and new_value != old_value:
            self.value_changed.emit(new_value)

    def option_buttons(self) -> list[QCheckBox]:
        """Return option widgets in visual order."""
        return list(self._button_by_value.values())

    def _handle_button_toggled(self, button, checked: bool) -> None:
        if not checked or not isinstance(button, QCheckBox):
            return
        self.value_changed.emit(self._value_by_button.get(button, ""))


class FocusWheelSpinBox(QSpinBox):
    """Spin box that never changes value from mouse wheel scrolling."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class FocusWheelDoubleSpinBox(QDoubleSpinBox):
    """Double spin box that never changes value from mouse wheel scrolling."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class FocusAwareWidget(QWidget):
    """A widget that clears child focus when the user clicks on empty space."""

    def mousePressEvent(self, event):  # type: ignore[override]
        if self.childAt(event.position().toPoint()) is None:
            self.clearFocus()
        super().mousePressEvent(event)
