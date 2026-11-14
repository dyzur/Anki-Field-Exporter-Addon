"""Field Exporter: right-click selected rows in the Browser to copy or save
the fields you configured for each note type.

Entry points
  Browser context menu -> "Copy fields to clipboard" / "Export fields to CSV…"
  Tools menu           -> "Field Exporter…" (choose which fields to export)
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from aqt import gui_hooks, mw
from aqt.qt import QAction, QApplication, QFileDialog
from aqt.utils import showWarning, tooltip

from . import exporter

ADDON_NAME = __name__
COPY_LABEL = "Copy fields to clipboard"
CSV_LABEL = "Export fields to CSV\u2026"
SETTINGS_LABEL = "Field Exporter settings\u2026"
TOOLS_LABEL = "Field Exporter\u2026"

_csv_directory: str = ""  # remembers the last folder used in this session


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _config() -> Dict[str, Any]:
    stored = None
    if mw is not None and getattr(mw, "addonManager", None) is not None:
        try:
            stored = mw.addonManager.getConfig(ADDON_NAME)
        except Exception:
            stored = None
    return exporter.normalize_config(stored)


def _save_config(config: Dict[str, Any]) -> None:
    """Persist through Anki (so a running session sees it) and to disk."""
    cfg = exporter.normalize_config(config)
    mw.addonManager.setConfig(ADDON_NAME, cfg)
    try:
        path = os.path.join(mw.addonManager.addonsFolder(), ADDON_NAME, "config.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(cfg, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except Exception:  # pragma: no cover - best effort
        traceback.print_exc()


def _selected_note_ids(browser) -> List[int]:
    """Note ids behind the current Browser selection (cards are collapsed)."""
    raw: List[int] = []
    for getter in ("selected_notes", "selectedNotes"):
        fn = getattr(browser, getter, None)
        if fn is None:
            continue
        try:
            raw = [int(nid) for nid in fn()]
        except Exception:
            raw = []
        if raw:
            break
    if not raw:
        # Fall back to card ids -> note ids (covers older Browser builds).
        fn = getattr(browser, "selected_cards", None) or getattr(
            browser, "selectedCards", None
        )
        if fn is not None and mw is not None:
            try:
                for cid in fn():
                    raw.append(int(mw.col.get_card(cid).nid))
            except Exception:
                pass

    # A note with several selected cards is only exported once.
    seen = set()
    ids: List[int] = []
    for note_id in raw:
        if note_id not in seen:
            seen.add(note_id)
            ids.append(note_id)
    return ids


def _collect(browser, note_ids: List[int]) -> Optional[exporter.ExportResult]:
    if not note_ids:
        tooltip("No notes selected", parent=browser, period=2000)
        return None
    result = exporter.collect_records(mw.col, note_ids, _config())
    if not result.records:
        message = "No notes to export."
        if result.skipped_notetypes:
            message += (
                " These note types are set to \"skip\" in the settings: %s"
                % ", ".join(result.skipped_notetypes)
            )
        showWarning(message, parent=browser)
        return None
    return result


def _hint(result: exporter.ExportResult, config: Dict[str, Any]) -> str:
    """Short explanation appended to the success tooltip."""
    parts: List[str] = []
    if result.skipped_notetypes:
        parts.append("skipped %s" % ", ".join(result.skipped_notetypes))
    if result.unconfigured_notetypes:
        if not config.get("notetype_fields"):
            parts.append(
                "no fields chosen yet \u2014 Tools \u2192 %s"
                % TOOLS_LABEL.rstrip("\u2026")
            )
        else:
            parts.append(
                "all fields used for %s" % ", ".join(result.unconfigured_notetypes)
            )
    return (" \u2014 " + "; ".join(parts)) if parts else ""


def _default_csv_directory(cfg: Dict[str, Any]) -> str:
    candidate = _csv_directory or cfg.get("csv_directory") or ""
    if candidate:
        try:
            if Path(candidate).expanduser().is_dir():
                return str(Path(candidate).expanduser())
        except OSError:
            pass
    return str(Path.home())


def _guarded(handler):
    """Keep a failure inside one action from taking Anki down."""

    def wrapper(*args, **kwargs) -> None:
        try:
            handler(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            traceback.print_exc()
            parent = args[0] if args and args[0] is not None else mw
            showWarning("Field Exporter failed:\n%s" % exc, parent=parent)

    return wrapper


# --------------------------------------------------------------------------
# actions
# --------------------------------------------------------------------------


@_guarded
def _copy_to_clipboard(browser) -> None:
    note_ids = _selected_note_ids(browser)
    result = _collect(browser, note_ids)
    if result is None:
        return

    cfg = _config()
    QApplication.clipboard().setText(exporter.to_clipboard_text(result.records, cfg))

    count = len(result.records)
    message = "Copied %s note%s to clipboard" % (count, "" if count == 1 else "s")
    tooltip(message + _hint(result, cfg), parent=browser, period=4000)


@_guarded
def _save_as_csv(browser) -> None:
    global _csv_directory

    note_ids = _selected_note_ids(browser)
    result = _collect(browser, note_ids)
    if result is None:
        return

    cfg = _config()
    suggested = os.path.join(
        _default_csv_directory(cfg),
        "anki-export-%s.csv" % datetime.now().strftime("%Y%m%d-%H%M%S"),
    )
    path, _selected_filter = QFileDialog.getSaveFileName(
        browser,
        "Export selected notes to CSV",
        suggested,
        "CSV files (*.csv);;All files (*)",
    )
    if not path:
        return
    if not path.lower().endswith(".csv"):
        path += ".csv"

    text = exporter.to_csv_text(result.records, cfg)
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            handle.write(text)
    except OSError as exc:
        showWarning("Could not write the file:\n%s" % exc, parent=browser)
        return

    _csv_directory = str(Path(path).parent)

    count = len(result.records)
    message = "Exported %s note%s to %s" % (
        count,
        "" if count == 1 else "s",
        Path(path).name,
    )
    tooltip(message + _hint(result, cfg), parent=browser, period=4000)


@_guarded
def _open_settings(parent=None) -> None:
    from . import settings

    parent = parent if parent is not None else mw
    dialog = settings.SettingsDialog(parent, mw.col, _config())
    if not dialog.exec():
        return
    _save_config(dialog.result_config())
    tooltip("Field Exporter settings saved", parent=parent, period=2500)


# --------------------------------------------------------------------------
# wiring
# --------------------------------------------------------------------------


def _on_browser_will_show_context_menu(browser, menu) -> None:
    try:
        count = len(_selected_note_ids(browser))
    except Exception:
        count = 0
    suffix = " (%s note%s)" % (count, "" if count == 1 else "s") if count else ""

    menu.addSeparator()

    copy_action = QAction(COPY_LABEL + suffix, menu)
    copy_action.setEnabled(count > 0)
    copy_action.triggered.connect(
        lambda _checked=False, b=browser: _copy_to_clipboard(b)
    )
    menu.addAction(copy_action)

    csv_action = QAction(CSV_LABEL + suffix, menu)
    csv_action.setEnabled(count > 0)
    csv_action.triggered.connect(lambda _checked=False, b=browser: _save_as_csv(b))
    menu.addAction(csv_action)

    menu.addSeparator()
    settings_action = QAction(SETTINGS_LABEL, menu)
    settings_action.triggered.connect(
        lambda _checked=False, b=browser: _open_settings(b)
    )
    menu.addAction(settings_action)


def _on_main_window_did_init() -> None:
    form = getattr(mw, "form", None)
    menu = getattr(form, "menuTools", None) if form is not None else None
    if menu is None:
        return
    action = QAction(TOOLS_LABEL, mw)
    action.triggered.connect(lambda _checked=False: _open_settings(mw))
    menu.addAction(action)


gui_hooks.browser_will_show_context_menu.append(_on_browser_will_show_context_menu)
gui_hooks.main_window_did_init.append(_on_main_window_did_init)
