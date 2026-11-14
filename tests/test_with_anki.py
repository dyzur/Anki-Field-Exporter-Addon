"""Integration test: run against a real (temporary) Anki collection.

Needs Anki's bundled Python, e.g.:

  /Applications/Anki.app/Contents/Frameworks/Python.framework/Versions/3.13/bin/python3 \
      tests/test_with_anki.py

Nothing here touches your real collection: it builds a throwaway one in a
temp directory.
"""

import csv
import io
import os
import shutil
import sys
import tempfile
import unittest

APP_PACKAGES = "/Applications/Anki.app/Contents/Resources/app_packages"
if os.path.isdir(APP_PACKAGES):
    sys.path.insert(0, APP_PACKAGES)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anki.collection  # noqa: E402  (import order matters for anki's circular imports)
from anki.collection import Collection  # noqa: E402

import exporter  # noqa: E402

CONFIG = {
    "notetype_fields": {"Basic": ["Front", "Back"], "Cloze": ["Text"]},
    "unconfigured_notetype": "all_fields",
    "include_header_row": True,
}


class RealCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.mkdtemp(prefix="field-exporter-test-")
        cls.col = Collection(os.path.join(cls.tempdir, "collection.anki2"))

        basic = cls.col.models.by_name("Basic")
        note = cls.col.new_note(basic)
        note["Front"] = "<div>Capital of <b>France</b>?</div><div>second line</div>"
        note["Back"] = "Paris &amp; more<br>extra"
        cls.col.add_note(note, 1)
        cls.basic_id = note.id

        cloze = cls.col.models.by_name("Cloze")
        note = cls.col.new_note(cloze)
        note["Text"] = "{{c1::Paris}} is in {{c2::France}}"
        cls.col.add_note(note, 1)
        cls.cloze_id = note.id

    @classmethod
    def tearDownClass(cls):
        cls.col.close()
        shutil.rmtree(cls.tempdir, ignore_errors=True)

    def test_collects_both_note_types_with_converted_html(self):
        result = exporter.collect_records(
            self.col, [self.basic_id, self.cloze_id], CONFIG
        )
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.records), 2)

        basic, cloze = result.records
        self.assertEqual(basic.notetype, "Basic")
        self.assertEqual(basic.values["Front"], "Capital of France?\nsecond line")
        self.assertEqual(basic.values["Back"], "Paris & more\nextra")
        self.assertEqual(cloze.values["Text"], "{{c1::Paris}} is in {{c2::France}}")

    def test_field_order_follows_config(self):
        cfg = {**CONFIG, "notetype_fields": {"Basic": ["Back", "Front"]}}
        result = exporter.collect_records(self.col, [self.basic_id], cfg)
        self.assertEqual(list(result.records[0].values), ["Back", "Front"])

    def test_csv_round_trip(self):
        result = exporter.collect_records(
            self.col, [self.basic_id, self.cloze_id], CONFIG
        )
        text = exporter.to_csv_text(result.records, CONFIG)
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[0], ["Front", "Back", "Text"])
        self.assertEqual(rows[1][0], "Capital of France?\nsecond line")
        self.assertEqual(rows[1][2], "")  # Basic has no Text field
        self.assertEqual(rows[2][2], "{{c1::Paris}} is in {{c2::France}}")

    def test_unknown_note_type_skip_mode(self):
        cfg = {**CONFIG, "notetype_fields": {}, "unconfigured_notetype": "skip"}
        result = exporter.collect_records(self.col, [self.basic_id], cfg)
        self.assertEqual(result.records, [])
        self.assertEqual(result.skipped_notetypes, ["Basic"])

    def test_all_fields_mode_for_unknown_note_type(self):
        cfg = {**CONFIG, "notetype_fields": {}, "unconfigured_notetype": "all_fields"}
        result = exporter.collect_records(self.col, [self.cloze_id], cfg)
        self.assertIn("Text", result.records[0].values)


if __name__ == "__main__":
    unittest.main(verbosity=2)
