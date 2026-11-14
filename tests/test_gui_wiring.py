"""GUI wiring test: Browser context menu -> clipboard / CSV, with real Qt.

Runs headless (offscreen Qt) against Anki's bundled Python:

  /Applications/Anki.app/Contents/Frameworks/Python.framework/Versions/3.13/bin/python3 \
      tests/test_gui_wiring.py

It builds a throwaway collection and a fake `mw`, so your real collection and
Anki itself are never opened.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import _anki_qt  # noqa: E402  (boots Qt + aqt)

from anki.collection import Collection  # noqa: E402
import aqt  # noqa: E402
from aqt import gui_hooks  # noqa: E402
from aqt.qt import QApplication, QMenu, QWidget  # noqa: E402


class FakeAddonManager:
    """Mirrors the real AddonManager API: getConfig + writeConfig."""

    def __init__(self, config):
        self.config = config
        self.written = []

    def getConfig(self, module):
        return dict(self.config)

    def writeConfig(self, module, config):
        self.config = dict(config)
        self.written.append(dict(config))

    def addonsFolder(self, module=None):
        return os.path.join(tempfile.gettempdir(), module) if module else tempfile.gettempdir()


class FakeMenu:
    def __init__(self):
        self.actions = []

    def addAction(self, action):
        self.actions.append(action)


class FakeForm:
    def __init__(self):
        self.menuTools = FakeMenu()


class FakeMw(QWidget):
    """Stands in for the real AnkiQt main window (so QAction parenting works)."""

    def __init__(self, col, config):
        super().__init__()
        self.col = col
        self.form = FakeForm()
        self.addonManager = FakeAddonManager(config)
        self.progress = MagicMock()


class FakeBrowser(QWidget):
    """Stands in for aqt.browser.Browser (a QWidget, so tooltips are happy)."""

    def __init__(self, note_ids):
        super().__init__()
        self._note_ids = list(note_ids)

    def selected_notes(self):
        return list(self._note_ids)


CONFIG = {
    "notetype_fields": {"Basic": ["Front", "Back"]},
    "unconfigured_notetype": "all_fields",
    "include_header_row": True,
    "csv_directory": "",
}


def load_addon():
    """Import the add-on as a package, exactly like Anki does."""
    import importlib.util

    name = "anki_field_exporter"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name,
        os.path.join(SRC, "__init__.py"),
        submodule_search_locations=[SRC],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


addon = load_addon()


class ContextMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.mkdtemp(prefix="field-exporter-gui-")
        cls.col = Collection(os.path.join(cls.tempdir, "collection.anki2"))
        notetype = cls.col.models.by_name("Basic")
        cls.note_ids = []
        for front, back in (
            ("<b>Hi</b><br>there", "Back, with comma"),
            ("Second", "Card"),
        ):
            note = cls.col.new_note(notetype)
            note["Front"] = front
            note["Back"] = back
            cls.col.add_note(note, 1)
            cls.note_ids.append(note.id)

        cls.mw = FakeMw(cls.col, CONFIG)
        aqt.mw = cls.mw
        addon.mw = cls.mw
        cls.addon = addon

    @classmethod
    def tearDownClass(cls):
        cls.col.close()
        shutil.rmtree(cls.tempdir, ignore_errors=True)

    def menu_for(self, note_ids):
        browser = FakeBrowser(note_ids)
        menu = QMenu()
        self.addon._on_browser_will_show_context_menu(browser, menu)
        return browser, menu

    def test_hooks_are_registered(self):
        self.assertIn(
            self.addon._on_browser_will_show_context_menu,
            gui_hooks.browser_will_show_context_menu._hooks,
        )
        self.assertIn(
            self.addon._on_main_window_did_init,
            gui_hooks.main_window_did_init._hooks,
        )

    def test_menu_has_copy_csv_and_settings_entries(self):
        _browser, menu = self.menu_for(self.note_ids)
        actions = menu.actions()
        self.assertEqual(len(actions), 5)
        self.assertTrue(actions[0].isSeparator())
        self.assertTrue(actions[1].text().startswith(self.addon.COPY_LABEL))
        self.assertTrue(actions[2].text().startswith(self.addon.CSV_LABEL))
        self.assertTrue(actions[3].isSeparator())
        self.assertEqual(actions[4].text(), self.addon.SETTINGS_LABEL)

    def test_count_in_label_counts_notes_once(self):
        _browser, menu = self.menu_for(
            [self.note_ids[0], self.note_ids[0], self.note_ids[1]]
        )
        self.assertIn("(2 notes)", menu.actions()[1].text())

    def test_export_actions_disabled_without_selection(self):
        _browser, menu = self.menu_for([])
        self.assertFalse(menu.actions()[1].isEnabled())
        self.assertFalse(menu.actions()[2].isEnabled())
        self.assertTrue(menu.actions()[4].isEnabled())  # settings always works

    def test_copy_puts_tab_separated_text_on_the_clipboard(self):
        _browser, menu = self.menu_for(self.note_ids)
        menu.actions()[1].trigger()
        text = QApplication.clipboard().text()
        self.assertEqual(
            text,
            'Front\tBack\n"Hi\nthere"\tBack, with comma\nSecond\tCard\n',
        )

    def test_tools_menu_entry_is_added(self):
        self.mw.form.menuTools.actions = []
        self.addon._on_main_window_did_init()
        texts = [action.text() for action in self.mw.form.menuTools.actions]
        self.assertEqual(texts, [self.addon.TOOLS_LABEL])

    def test_hint_mentions_unconfigured_note_types(self):
        result = self.addon.exporter.ExportResult(
            records=[], unconfigured_notetypes=["Weird"]
        )
        hint = self.addon._hint(result, CONFIG)
        self.assertIn("Weird", hint)
        # no config at all -> point at the settings dialog
        hint = self.addon._hint(result, self.addon.exporter.normalize_config(None))
        self.assertIn("Tools", hint)

class SetConfigOnlyManager:
    """An Anki build that names its config writer ``setConfig``."""

    def __init__(self):
        self.config = {}
        self.calls = 0

    def getConfig(self, module):
        return dict(self.config)

    def setConfig(self, module, config):
        self.config = dict(config)
        self.calls += 1


class NoWriterManager:
    """An Anki build with no usable config writer at all."""

    def __init__(self, folder):
        self.folder = folder

    def getConfig(self, module):
        return None

    def addonsFolder(self, module=None):
        if module is None:
            return self.folder
        return os.path.join(self.folder, module)


class SaveConfigTests(unittest.TestCase):
    """Saving from the settings dialog must use the API this Anki really has."""

    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="field-exporter-save-")
        self.previous_mw = addon.mw
        self.previous_aqt_mw = aqt.mw

    def tearDown(self):
        addon.mw = self.previous_mw
        aqt.mw = self.previous_aqt_mw
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def use_manager(self, manager):
        fake = FakeMw(None, {})
        fake.addonManager = manager
        addon.mw = fake
        return fake

    def test_uses_writeConfig(self):
        manager = FakeAddonManager({})
        self.use_manager(manager)
        addon._save_config({"notetype_fields": {"Basic": ["Front"]}})
        self.assertEqual(len(manager.written), 1)
        self.assertEqual(manager.written[0]["notetype_fields"], {"Basic": ["Front"]})
        # the next export picks the saved config up
        self.assertEqual(addon._config()["notetype_fields"], {"Basic": ["Front"]})

    def test_falls_back_to_setConfig(self):
        manager = SetConfigOnlyManager()
        self.use_manager(manager)
        addon._save_config({"notetype_fields": {"Cloze": ["Text"]}})
        self.assertEqual(manager.calls, 1)
        self.assertEqual(manager.config["notetype_fields"], {"Cloze": ["Text"]})

    def test_falls_back_to_writing_config_json(self):
        self.use_manager(NoWriterManager(self.tempdir))
        addon._save_config({"notetype_fields": {"Basic": ["Back"]}})
        path = os.path.join(self.tempdir, addon.ADDON_NAME, "config.json")
        with open(path, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["notetype_fields"], {"Basic": ["Back"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
