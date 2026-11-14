"""Unit tests for exporter.py — no Anki required.

Run with:  python3 tests/test_exporter.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import exporter  # noqa: E402


class FakeNote:
    def __init__(self, note_id, notetype_name, field_names, values):
        self.id = note_id
        self.fields = list(values)
        self._notetype = {
            "name": notetype_name,
            "flds": [{"name": name} for name in field_names],
        }

    def note_type(self):
        return self._notetype


class FakeCol:
    def __init__(self, notes):
        self._notes = {note.id: note for note in notes}

    def get_note(self, note_id):
        try:
            return self._notes[note_id]
        except KeyError:
            raise Exception("not found")


def basic(note_id, front, back="", name="Basic"):
    return FakeNote(note_id, name, ["Front", "Back"], [front, back])


CONFIG = {
    "notetype_fields": {"Basic": ["Front", "Back"], "Cloze": ["Text"]},
    "unconfigured_notetype": "all_fields",
    "include_header_row": True,
    "csv_directory": "",
}


class HtmlToTextTests(unittest.TestCase):
    def test_plain_text_is_untouched(self):
        self.assertEqual(exporter.html_to_text("just text"), "just text")

    def test_bold_and_br(self):
        self.assertEqual(
            exporter.html_to_text("Hello <b>world</b><br>second line"),
            "Hello world\nsecond line",
        )

    def test_div_lines(self):
        self.assertEqual(
            exporter.html_to_text("<div>one</div><div>two</div>"), "one\ntwo"
        )

    def test_nested_blocks_do_not_become_empty_lines(self):
        self.assertEqual(
            exporter.html_to_text("<div><div>a</div><div>b</div></div>"), "a\nb"
        )

    def test_entities_are_decoded(self):
        self.assertEqual(
            exporter.html_to_text("Tom &amp; Jerry&nbsp;rule &lt;3"),
            "Tom & Jerry rule <3",
        )

    def test_whitespace_is_collapsed_per_line(self):
        self.assertEqual(
            exporter.html_to_text("<div>a    b\n\tc</div>"), "a b c"
        )

    def test_lists(self):
        self.assertEqual(
            exporter.html_to_text("<ul><li>one</li><li>two</li></ul>"), "one\ntwo"
        )

    def test_image_marker_is_kept(self):
        self.assertEqual(
            exporter.html_to_text('Look <img src="pic.jpg"> here'),
            "Look [image: pic.jpg] here",
        )

    def test_style_block_is_dropped(self):
        self.assertEqual(
            exporter.html_to_text("<style>.x{color:red}</style>visible"),
            "visible",
        )

    def test_empty_values(self):
        self.assertEqual(exporter.html_to_text(""), "")
        self.assertEqual(exporter.html_to_text(None), "")

    def test_cloze_markup_is_preserved(self):
        self.assertEqual(
            exporter.html_to_text("{{c1::Paris}} is the capital"),
            "{{c1::Paris}} is the capital",
        )


class ConfigTests(unittest.TestCase):
    def test_defaults_when_empty(self):
        cfg = exporter.normalize_config(None)
        self.assertEqual(cfg["notetype_fields"], {})  # nothing picked yet
        self.assertEqual(cfg["unconfigured_notetype"], exporter.UNCONFIGURED_ALL)
        self.assertTrue(cfg["include_header_row"])
        self.assertEqual(cfg["csv_directory"], "")

    def test_defaults_fall_back_to_all_fields(self):
        cfg = exporter.normalize_config(None)
        self.assertEqual(
            exporter.resolve_fields("Basic", ["Front", "Back"], cfg),
            ["Front", "Back"],
        )

    def test_string_field_is_coerced_to_list(self):
        cfg = exporter.normalize_config({"notetype_fields": {"Basic": "Front"}})
        self.assertEqual(cfg["notetype_fields"]["Basic"], ["Front"])

    def test_blank_field_names_are_dropped(self):
        cfg = exporter.normalize_config(
            {"notetype_fields": {"Basic": ["Front", "", "  "]}}
        )
        self.assertEqual(cfg["notetype_fields"]["Basic"], ["Front"])

    def test_bad_unconfigured_mode_falls_back(self):
        cfg = exporter.normalize_config({"unconfigured_notetype": "nonsense"})
        self.assertEqual(cfg["unconfigured_notetype"], "all_fields")

    def test_skip_mode_accepted(self):
        cfg = exporter.normalize_config({"unconfigured_notetype": "SKIP"})
        self.assertEqual(cfg["unconfigured_notetype"], "skip")


class ResolveFieldsTests(unittest.TestCase):
    def test_configured_notetype(self):
        cfg = exporter.normalize_config(CONFIG)
        self.assertEqual(
            exporter.resolve_fields("Basic", ["Front", "Back", "Extra"], cfg),
            ["Front", "Back"],
        )

    def test_notetype_match_is_case_insensitive(self):
        cfg = exporter.normalize_config(CONFIG)
        self.assertEqual(
            exporter.resolve_fields("basic", ["Front", "Back"], cfg),
            ["Front", "Back"],
        )

    def test_unconfigured_uses_all_fields(self):
        cfg = exporter.normalize_config(CONFIG)
        self.assertEqual(
            exporter.resolve_fields("Image Occlusion", ["A", "B"], cfg), ["A", "B"]
        )

    def test_unconfigured_skip_returns_none(self):
        cfg = exporter.normalize_config(
            {**CONFIG, "unconfigured_notetype": "skip"}
        )
        self.assertIsNone(exporter.resolve_fields("Other", ["A"], cfg))


class CollectRecordsTests(unittest.TestCase):
    def test_html_is_converted_and_fields_selected(self):
        col = FakeCol([basic(1, "<b>Q</b><br>more", "A")])
        result = exporter.collect_records(col, [1], CONFIG)
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record.notetype, "Basic")
        self.assertEqual(record.values, {"Front": "Q\nmore", "Back": "A"})

    def test_duplicate_note_ids_are_collapsed(self):
        col = FakeCol([basic(1, "Q", "A")])
        result = exporter.collect_records(col, [1, 1, 1], CONFIG)
        self.assertEqual(len(result.records), 1)

    def test_missing_field_becomes_blank(self):
        col = FakeCol([basic(1, "Q", "A")])
        cfg = {
            "notetype_fields": {"Basic": ["Front", "Nope"]},
            "unconfigured_notetype": "all_fields",
        }
        result = exporter.collect_records(col, [1], cfg)
        self.assertEqual(result.records[0].values, {"Front": "Q", "Nope": ""})

    def test_skipped_notetype_is_reported(self):
        col = FakeCol([basic(1, "Q", "A", name="Weird")])
        cfg = {**CONFIG, "unconfigured_notetype": "skip"}
        result = exporter.collect_records(col, [1], cfg)
        self.assertEqual(result.records, [])
        self.assertEqual(result.skipped_notetypes, ["Weird"])
        self.assertEqual(result.unconfigured_notetypes, [])

    def test_unconfigured_notetype_is_reported_once(self):
        col = FakeCol(
            [
                basic(1, "Q", "A", name="Weird"),
                basic(2, "Q2", "A2", name="Weird"),
                basic(3, "Q3", "A3"),
            ]
        )
        cfg = {"notetype_fields": {"Basic": ["Front"]}}
        result = exporter.collect_records(col, [1, 2, 3], cfg)
        self.assertEqual(result.unconfigured_notetypes, ["Weird"])
        self.assertEqual(len(result.records), 3)
        # the unconfigured note type still exports all its fields
        self.assertEqual(result.records[0].values, {"Front": "Q", "Back": "A"})

    def test_configured_notetype_never_flagged(self):
        col = FakeCol([basic(1, "Q", "A")])
        result = exporter.collect_records(col, [1], CONFIG)
        self.assertEqual(result.unconfigured_notetypes, [])

    def test_is_configured_is_case_insensitive(self):
        cfg = exporter.normalize_config(CONFIG)
        self.assertTrue(exporter.is_configured("basic", cfg))
        self.assertFalse(exporter.is_configured("Other", cfg))

    def test_broken_note_is_reported_not_raised(self):
        col = FakeCol([])
        result = exporter.collect_records(col, [99], CONFIG)
        self.assertEqual(result.records, [])
        self.assertEqual(len(result.errors), 1)

    def test_order_follows_selection(self):
        col = FakeCol([basic(1, "A"), basic(2, "B"), basic(3, "C")])
        result = exporter.collect_records(col, [3, 1, 2], CONFIG)
        self.assertEqual([r.note_id for r in result.records], [3, 1, 2])


class SerializationTests(unittest.TestCase):
    def setUp(self):
        self.col = FakeCol(
            [
                basic(1, "Front, with comma", "Back <b>one</b>"),
                FakeNote(2, "Cloze", ["Text"], ["{{c1::Two}}"]),
            ]
        )
        self.result = exporter.collect_records(self.col, [1, 2], CONFIG)

    def test_header_is_union_in_first_seen_order(self):
        header, rows = exporter.build_table(self.result.records)
        self.assertEqual(header, ["Front", "Back", "Text"])
        self.assertEqual(rows[0], ["Front, with comma", "Back one", ""])
        self.assertEqual(rows[1], ["", "", "{{c1::Two}}"])

    def test_csv_quotes_commas_and_uses_crlf(self):
        text = exporter.to_csv_text(self.result.records, CONFIG)
        lines = text.split("\r\n")
        self.assertEqual(lines[0], "Front,Back,Text")
        self.assertIn('"Front, with comma",Back one,', text)

    def test_header_can_be_suppressed(self):
        cfg = {**CONFIG, "include_header_row": False}
        text = exporter.to_csv_text(self.result.records, cfg)
        self.assertFalse(text.startswith("Front"))

    def test_clipboard_is_tab_separated_with_lf(self):
        text = exporter.to_clipboard_text(self.result.records, CONFIG)
        self.assertTrue(text.startswith("Front\tBack\tText\n"))
        self.assertNotIn("\r\n", text)

    def test_multiline_cell_is_quoted_in_csv(self):
        col = FakeCol([basic(1, "line1<br>line2", "A")])
        result = exporter.collect_records(col, [1], CONFIG)
        text = exporter.to_csv_text(result.records, CONFIG)
        self.assertIn('"line1\nline2"', text)
        # and it round-trips through the csv module
        import csv
        import io

        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(rows[1][0], "line1\nline2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
