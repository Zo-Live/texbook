"""Modal dialogs used by the TexBook GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from texbook.gui.display import (
    DEFAULT_GUI_FONT_FAMILY,
    DEFAULT_GUI_FONT_POINT_SIZE,
    GUI_FONT_FALLBACKS,
    GuiDisplayPreferences,
)
from texbook.gui.i18n import tr
from texbook.gui.theme import build_combo_popup_style
from texbook.gui.widgets import FocusWheelComboBox, FocusWheelSpinBox


class AboutDialog(QDialog):
    """Non-maximizable about dialog that follows the current GUI theme."""

    def __init__(self, parent: QWidget | None = None, *, app_name: str, preferences: GuiDisplayPreferences) -> None:
        super().__init__(parent)
        self.setObjectName("aboutDialog")
        self.setWindowTitle(tr(preferences.language, "dialog.about.title", app_name=app_name))
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(Qt.WindowType.MSWindowsFixedSizeDialogHint, True)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        header = QLabel(app_name, self)
        header.setObjectName("aboutDialogTitle")
        header.setProperty("sectionTitle", True)
        layout.addWidget(header)

        body = QLabel(tr(preferences.language, "dialog.about.text", app_name=app_name), self)
        body.setProperty("muted", True)
        body.setWordWrap(True)
        layout.addWidget(body)

        info = QLabel(tr(preferences.language, "dialog.about.informative", app_name=app_name), self)
        info.setObjectName("aboutDialogInfo")
        info.setWordWrap(True)
        info.setProperty("muted", True)
        layout.addWidget(info)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class SettingsDialog(QDialog):
    """Modal settings dialog for GUI display preferences."""

    preferences_applied = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        preferences: GuiDisplayPreferences,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsDialog")
        self._preferences = preferences
        self.setWindowTitle(tr(self._preferences.language, "dialog.settings.title"))
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, False)
        self.setWindowFlag(Qt.WindowType.MSWindowsFixedSizeDialogHint, True)
        self.setModal(True)
        self._initial_preferences = preferences

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        intro = QLabel(tr(self._preferences.language, "dialog.settings.intro"), self)
        intro.setProperty("muted", True)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.font_family_combo = FocusWheelComboBox(self)
        self.font_family_combo.setEditable(True)
        self.font_family_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.font_family_combo.setObjectName("settingsFontFamilyCombo")
        self.font_family_combo.addItems(self._font_candidates())
        self.font_family_combo.setCurrentText(preferences.font_family)
        self.font_family_combo.set_popup_style(
            build_combo_popup_style(
                self._preferences.theme,
                font_family=self._preferences.font_family,
                font_point_size=self._preferences.font_point_size,
            )
        )
        form.addRow(tr(self._preferences.language, "dialog.settings.font_family"), self.font_family_combo)

        self.font_point_size_spin = FocusWheelSpinBox(self)
        self.font_point_size_spin.setObjectName("settingsFontSizeSpinBox")
        self.font_point_size_spin.setRange(8, 24)
        self.font_point_size_spin.setValue(preferences.font_point_size)
        form.addRow(tr(self._preferences.language, "dialog.settings.font_size"), self.font_point_size_spin)

        layout.addLayout(form)

        self.reset_button = QPushButton(tr(self._preferences.language, "dialog.settings.reset"), self)
        self.reset_button.setObjectName("settingsResetButton")
        self.reset_button.clicked.connect(self._reset_to_defaults)
        layout.addWidget(self.reset_button, alignment=Qt.AlignmentFlag.AlignLeft)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _font_candidates(self) -> list[str]:
        families = list(GUI_FONT_FALLBACKS)
        families.extend(QFontDatabase.families())
        seen: set[str] = set()
        ordered: list[str] = []
        for family in families:
            if family in seen:
                continue
            seen.add(family)
            ordered.append(family)
        return ordered

    def _reset_to_defaults(self) -> None:
        self.font_family_combo.setCurrentText(DEFAULT_GUI_FONT_FAMILY)
        self.font_point_size_spin.setValue(DEFAULT_GUI_FONT_POINT_SIZE)

    def _accept(self) -> None:
        family = self.font_family_combo.currentText().strip() or DEFAULT_GUI_FONT_FAMILY
        point_size = self.font_point_size_spin.value()
        self._preferences = GuiDisplayPreferences(
            theme=self._initial_preferences.theme,
            language=self._initial_preferences.language,
            font_family=family,
            font_point_size=point_size,
        )
        self.preferences_applied.emit(self._preferences)
        self.accept()

    def selected_preferences(self) -> GuiDisplayPreferences:
        return self._preferences
