"""Settings dialog: tick the fields you want exported, per note type.

Kept separate from `__init__.py` so the export logic stays free of Qt imports
and the dialog can be exercised on its own.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from aqt.qt import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    Qt,
    QVBoxLayout,
)

from . import exporter

# Qt5 exposes these as flat attributes, Qt6 groups them in enums.
_CheckState = getattr(Qt, "CheckState", Qt)
_ItemFlag = getattr(Qt, "ItemFlag", Qt)

CHECKED = _CheckState.Checked
UNCHECKED = _CheckState.Unchecked
PARTIALLY = _CheckState.PartiallyChecked

ITEM_FLAGS = (
    _ItemFlag.ItemIsUserCheckable
    | _ItemFlag.ItemIsAutoTristate
    | _ItemFlag.ItemIsEnabled
)

UNCONFIGURED_CHOICES = (
    ("Export all of its fields", exporter.UNCONFIGURED_ALL),
    ("Skip these notes", exporter.UNCONFIGURED_SKIP),
)


class SettingsDialog(QDialog):
    """Pick, per note type, which fields the exporter should copy out."""

    def __init__(self, parent, col, config: Optional[Dict[str, Any]]) -> None:
        super().__init__(parent)
        self.col = col
        self._config = exporter.normalize_config(config)
        self._note_types: List[Dict[str, Any]] = []

        self.setWindowTitle("Field Exporter Settings")
        self.resize(600, 680)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Tick the fields to export for each note type. "
            "Column order in the export follows each note type's field order."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter note types\u2026")
        self.filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_edit)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Note type / field"])
        self.tree.setUniformRowHeights(True)
        self.tree.setColumnWidth(0, 420)
        layout.addWidget(self.tree, 1)

        options_title = QLabel("Notes of a note type you have not ticked:")
        layout.addWidget(options_title)

        self.unconfigured_combo = QComboBox()
        for label, value in UNCONFIGURED_CHOICES:
            self.unconfigured_combo.addItem(label, value)
        layout.addWidget(self.unconfigured_combo)

        self.header_check = QCheckBox("Include a header row with the field names")
        layout.addWidget(self.header_check)

        directory_row = QHBoxLayout()
        directory_row.addWidget(QLabel("Default folder for CSV files:"))
        self.directory_edit = QLineEdit()
        self.directory_edit.setPlaceholderText("(home folder)")
        directory_row.addWidget(self.directory_edit, 1)
        browse_button = QPushButton("Browse\u2026")
        browse_button.clicked.connect(self._browse_directory)
        directory_row.addWidget(browse_button)
        layout.addLayout(directory_row)

        buttons = QHBoxLayout()
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self._reset)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("Save")
        save_button.setDefault(True)
        save_button.clicked.connect(self.accept)
        buttons.addWidget(reset_button)
        buttons.addStretch(1)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

        self._load(self._config)
        self.filter_edit.setFocus()

    # -- population ------------------------------------------------------

    def _load(self, config: Dict[str, Any]) -> None:
        self._note_types = self._note_types_from_collection()
        self.tree.clear()
        self._items: Dict[str, QTreeWidgetItem] = {}

        mapping = config.get("notetype_fields") or {}
        lowered = {str(key).lower(): value for key, value in mapping.items()}

        for notetype in self._note_types:
            name = notetype.get("name") or ""
            if not name:
                continue
            fields = [f.get("name", "") for f in notetype.get("flds", [])]

            top = QTreeWidgetItem(self.tree, [name])
            top.setFlags(top.flags() | ITEM_FLAGS)
            self._items[name] = top

            wanted = mapping.get(name)
            if wanted is None:
                wanted = lowered.get(name.lower())
            wanted_set = {str(f) for f in (wanted or [])}

            has_checked = False
            for field_name in fields:
                child = QTreeWidgetItem(top, [field_name])
                child.setFlags(child.flags() | ITEM_FLAGS)
                checked = field_name in wanted_set
                child.setCheckState(0, CHECKED if checked else UNCHECKED)
                has_checked = has_checked or checked

            top.setExpanded(has_checked)

        self.unconfigured_combo.setCurrentIndex(
            max(
                0,
                self.unconfigured_combo.findData(
                    config.get("unconfigured_notetype")
                ),
            )
        )
        self.header_check.setChecked(bool(config.get("include_header_row", True)))
        self.directory_edit.setText(str(config.get("csv_directory") or ""))
        self._apply_filter(self.filter_edit.text())

    def _note_types_from_collection(self) -> List[Dict[str, Any]]:
        try:
            notetypes = list(self.col.models.all())
        except Exception:
            return []
        notetypes.sort(key=lambda nt: (nt.get("name") or "").lower())
        return notetypes

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            matches = not needle or needle in item.text(0).lower()
            item.setHidden(not matches)
            if needle and matches:
                item.setExpanded(True)

    # -- reading the result ----------------------------------------------

    def selected_notetype_fields(self) -> Dict[str, List[str]]:
        mapping: Dict[str, List[str]] = {}
        for index in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(index)
            chosen = [
                top.child(child).text(0)
                for child in range(top.childCount())
                if top.child(child).checkState(0) == CHECKED
            ]
            if chosen:
                mapping[top.text(0)] = chosen
        return mapping

    def result_config(self) -> Dict[str, Any]:
        return exporter.normalize_config(
            {
                "notetype_fields": self.selected_notetype_fields(),
                "unconfigured_notetype": self.unconfigured_combo.currentData()
                or exporter.UNCONFIGURED_ALL,
                "include_header_row": self.header_check.isChecked(),
                "csv_directory": self.directory_edit.text().strip(),
            }
        )

    # -- actions ---------------------------------------------------------

    def _browse_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Choose the default CSV folder", self.directory_edit.text()
        )
        if directory:
            self.directory_edit.setText(directory)

    def _reset(self) -> None:
        self.filter_edit.clear()
        defaults = exporter.normalize_config(None)
        # Clear every tick, keep the note type list on screen.
        for index in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(index)
            for child in range(top.childCount()):
                top.child(child).setCheckState(0, UNCHECKED)
            top.setExpanded(False)
        self.unconfigured_combo.setCurrentIndex(
            max(0, self.unconfigured_combo.findData(defaults["unconfigured_notetype"]))
        )
        self.header_check.setChecked(defaults["include_header_row"])
        self.directory_edit.setText(defaults["csv_directory"])
        self._apply_filter("")
