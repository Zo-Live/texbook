"""Reusable widgets for the TexBook GUI interface layer."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from texbook.gui.theme import ComboPopupStyle


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


def close_combo_popup(combo_box: QComboBox) -> None:
    """Hide a combo box popup if it is currently visible."""
    view = combo_box.view()
    if view is None or not view.isVisible():
        return
    combo_box.hidePopup()


def _application_combo_boxes() -> list[QComboBox]:
    app = QApplication.instance()
    if app is None:
        return []
    combo_boxes: list[QComboBox] = []
    seen: set[int] = set()
    for widget in app.topLevelWidgets():
        for combo_box in widget.findChildren(QComboBox):
            combo_id = id(combo_box)
            if combo_id in seen:
                continue
            seen.add(combo_id)
            combo_boxes.append(combo_box)
    return combo_boxes


def close_combo_popups(root: QWidget | None = None, *, exclude: QComboBox | None = None) -> None:
    """Close visible combo-box popups without directly closing Qt popup windows."""
    combo_boxes: list[QComboBox] = (
        root.findChildren(QComboBox) if root is not None else _application_combo_boxes()
    )

    for combo_box in combo_boxes:
        if combo_box is exclude:
            continue
        close_combo_popup(combo_box)


class ComboPopupItemDelegate(QStyledItemDelegate):
    """Paint combo popup items with explicit theme colors."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup_style: ComboPopupStyle | None = None

    def set_popup_style(self, style: ComboPopupStyle) -> None:
        """Update colors used when painting popup list items."""
        self._popup_style = style

    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        if self._popup_style is None:
            super().paint(painter, option, index)
            return

        item_option = QStyleOptionViewItem(option)
        self.initStyleOption(item_option, index)

        selected = bool(item_option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(item_option.state & QStyle.StateFlag.State_MouseOver)
        enabled = bool(item_option.state & QStyle.StateFlag.State_Enabled)

        background = self._popup_style.background
        foreground = self._popup_style.text
        if selected:
            background = self._popup_style.selected_background
            foreground = self._popup_style.selected_text
        elif hovered:
            background = self._popup_style.hover_background
            foreground = self._popup_style.hover_text
        if not enabled:
            foreground = self._popup_style.disabled_text

        painter.save()
        painter.fillRect(item_option.rect, background)
        painter.setPen(foreground)
        painter.setFont(item_option.font)
        text_rect = item_option.rect.adjusted(10, 0, -10, 0)
        text = item_option.fontMetrics.elidedText(
            item_option.text,
            Qt.TextElideMode.ElideRight,
            max(0, text_rect.width()),
        )
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        painter.restore()

    def sizeHint(self, option, index):  # type: ignore[override]
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), option.fontMetrics.height() + 12))
        return size


class FocusWheelComboBox(QComboBox):
    """Combo box that never changes value from mouse wheel scrolling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup_style: ComboPopupStyle | None = None
        self._popup_delegate = ComboPopupItemDelegate(self)
        self._popup_view = QListView(self)
        self._popup_view.setObjectName("comboPopupView")
        self._popup_view.setItemDelegate(self._popup_delegate)
        self._popup_view.setUniformItemSizes(False)
        self.setView(self._popup_view)

    def set_popup_style(self, style: ComboPopupStyle) -> None:
        """Store and apply the direct popup style used by detached Qt popup windows."""
        self._popup_style = style
        self._popup_delegate.set_popup_style(style)
        self._apply_popup_style()

    def _apply_popup_style(self) -> None:
        if self._popup_style is None:
            return
        view = self.view()
        if view is None:
            return

        palette = QPalette(self._popup_style.palette)
        view.setStyleSheet(self._popup_style.view_stylesheet)
        view.setPalette(palette)
        view.setItemDelegate(self._popup_delegate)
        view.setAutoFillBackground(True)
        view.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        viewport = view.viewport()
        if viewport is not None:
            viewport.setPalette(QPalette(self._popup_style.palette))
            viewport.setAutoFillBackground(True)

        popup_window = view.window()
        if popup_window is not None and popup_window is not self.window():
            popup_window.setStyleSheet(self._popup_style.window_stylesheet)
            popup_window.setPalette(QPalette(self._popup_style.palette))
            popup_window.setAutoFillBackground(True)
            popup_window.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def showPopup(self) -> None:
        close_combo_popups(self.window(), exclude=self)
        self._apply_popup_style()
        super().showPopup()
        self._apply_popup_style()

    def hidePopup(self) -> None:
        super().hidePopup()

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


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
