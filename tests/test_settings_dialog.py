"""Settings dialog test: population, filter, save payload, reset.

Headless Qt, Anki's bundled Python:

  /Applications/Anki.app/Contents/Frameworks/Python.framework/Versions/3.13/bin/python3 \
      tests/test_settings_dialog.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import _anki_qt  # noqa: E402  (boots Qt + aqt)

import importlib.util  # noqa: E402


def load_addon_package():
    name = "anki_field_exporter"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(SRC, "__init__.py"), submodule_search_locations=[SRC]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load_addon_package()
import anki_field_exporter.settings as settings  # noqa: E402  (lazy in __init__)

CHECKED = settings.CHECKED
UNCHECKED = settings.UNCHECKED


class FakeModelManager:
    def __init__(self, notetypes):
        self._notetypes = notetypes

    def all(self):
        return [dict(notetype) for notetype in self._notetypes]


class FakeCol:
    def __init__(self, notetypes):
        self.models = FakeModelManager(notetypes)


def notetype(name, fields):
    return {"name": name, "flds": [{"name": f} for f in fields]}


NOTETYPES = [
    notetype("Basic", ["Front", "Back"]),
    notetype("Cloze", ["Text", "Extra"]),
    notetype("Image Occlusion", ["Image", "Question", "Answer"]),
]

CONFIG = {
    "notetype_fields": {"Cloze": ["Text"]},
    "unconfigured_notetype": "skip",
    "include_header_row": False,
    "csv_directory": "/tmp/anki-exports",
}


class SettingsDialogTests(unittest.TestCase):
    def make_dialog(self, config=CONFIG):
        return settings.SettingsDialog(None, FakeCol(NOTETYPES), config)

    def top_items(self, dialog):
        return {
            dialog.tree.topLevelItem(i).text(0): dialog.tree.topLevelItem(i)
            for i in range(dialog.tree.topLevelItemCount())
        }

    def test_lists_every_notetype_sorted(self):
        dialog = self.make_dialog()
        self.assertEqual(
            list(self.top_items(dialog)),
            ["Basic", "Cloze", "Image Occlusion"],
        )

    def test_existing_config_is_ticked(self):
        dialog = self.make_dialog()
        cloze = self.top_items(dialog)["Cloze"]
        states = {
            cloze.child(i).text(0): cloze.child(i).checkState(0)
            for i in range(cloze.childCount())
        }
        self.assertEqual(states, {"Text": CHECKED, "Extra": UNCHECKED})

    def test_untouched_dialog_round_trips_the_config(self):
        dialog = self.make_dialog()
        result = dialog.result_config()
        self.assertEqual(result["notetype_fields"], {"Cloze": ["Text"]})
        self.assertEqual(result["unconfigured_notetype"], "skip")
        self.assertFalse(result["include_header_row"])
        self.assertEqual(result["csv_directory"], "/tmp/anki-exports")

    def test_ticking_a_field_saves_it_in_notetype_order(self):
        dialog = self.make_dialog()
        basic = self.top_items(dialog)["Basic"]
        # tick the second field first: order must still follow the note type
        basic.child(1).setCheckState(0, CHECKED)
        basic.child(0).setCheckState(0, CHECKED)
        result = dialog.result_config()
        self.assertEqual(result["notetype_fields"]["Basic"], ["Front", "Back"])

    def test_unticking_everything_drops_the_notetype(self):
        dialog = self.make_dialog()
        cloze = self.top_items(dialog)["Cloze"]
        cloze.child(0).setCheckState(0, UNCHECKED)
        self.assertEqual(dialog.result_config()["notetype_fields"], {})

    def test_ticking_the_parent_ticks_all_its_fields(self):
        dialog = self.make_dialog()
        occ = self.top_items(dialog)["Image Occlusion"]
        occ.setCheckState(0, CHECKED)
        self.assertEqual(
            dialog.result_config()["notetype_fields"],
            {"Cloze": ["Text"], "Image Occlusion": ["Image", "Question", "Answer"]},
        )

    def test_partial_state_when_only_some_fields_ticked(self):
        dialog = self.make_dialog()
        cloze = self.top_items(dialog)["Cloze"]
        self.assertEqual(cloze.checkState(0), settings.PARTIALLY)

    def test_filter_hides_non_matching_notetypes(self):
        dialog = self.make_dialog()
        dialog.filter_edit.setText("image")
        items = self.top_items(dialog)
        self.assertTrue(items["Basic"].isHidden())
        self.assertTrue(items["Cloze"].isHidden())
        self.assertFalse(items["Image Occlusion"].isHidden())

    def test_reset_clears_everything(self):
        dialog = self.make_dialog()
        dialog._reset()
        result = dialog.result_config()
        self.assertEqual(result["notetype_fields"], {})
        self.assertEqual(result["unconfigured_notetype"], "all_fields")
        self.assertTrue(result["include_header_row"])
        self.assertEqual(result["csv_directory"], "")

    def test_empty_config_shows_nothing_ticked(self):
        dialog = self.make_dialog({})
        for name, item in self.top_items(dialog).items():
            for index in range(item.childCount()):
                self.assertEqual(
                    item.child(index).checkState(0), UNCHECKED, name
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
