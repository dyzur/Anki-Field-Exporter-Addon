# Field Exporter for Anki

Right-click any selection in Anki's **Browser** and either copy the fields you
care about to the clipboard, or save them as a `.csv`. Which fields get exported
is set once per note type — pick them in a dialog, no JSON needed.

Built for people who reuse their card content elsewhere: pasting into notes,
docs, spreadsheets, or an LLM.

## Usage

1. **Tools → Field Exporter…** → tick the fields you want for each note type
   (use the filter box if you have many) → **Save**.
2. In the Browser, select the notes you want and **right-click**:

```
────────────────────────────
Copy fields to clipboard (12 notes)
Export fields to CSV… (12 notes)
────────────────────────────
Field Exporter settings…
```

- **Copy fields to clipboard** — tab-separated text with a header row; paste
  straight into Excel, Numbers, Google Sheets, or a text field.
- **Export fields to CSV…** — save dialog with a timestamped default name.
  Written as UTF-8 with BOM so Excel and Numbers show accented characters
  correctly.
- Both entries grey out when nothing is selected, and the count is the number of
  *notes* — a note with several selected cards is exported once.

Note types you haven't configured follow the **Notes of a note type you have not
ticked** option: export all of their fields, or skip them. The tooltip after each
export tells you which path was taken.

## Output format

- Field HTML becomes plain text: `<br>` and block ends become line breaks,
  entities are decoded, images become `[image: filename]`, `<style>`/`<script>`
  are dropped. Cloze markup (`{{c1::…}}`) and `[sound:…]` are kept as-is.
- Clipboard text is TSV with `\n` line endings; CSV is comma-separated,
  RFC-4180 quoted, `\r\n` line endings.
- A cell containing a comma, tab, quote or line break is quoted in both formats,
  so multi-line fields keep their shape.

## Install

**From AnkiWeb:** Tools → Add-ons → Get Add-ons… → paste the add-on code.

**Manual / development:**

```bash
make install       # rsync into addons21/anki_field_exporter
```

Restart Anki afterwards. An existing `config.json` is never overwritten, so your
settings survive updates.

Requires Anki 2.1.50 or newer (desktop). Not compatible with AnkiMobile or
AnkiDroid — they cannot run add-ons.

## Configuration

Everything can be set in the dialog. The equivalent JSON lives in
**Tools → Add-ons → Field Exporter → Config** (see `config.md` there too):

```json
{
  "notetype_fields": {
    "Basic": ["Front", "Back"]
  },
  "unconfigured_notetype": "all_fields",
  "include_header_row": true,
  "csv_directory": ""
}
```

`notetype_fields` maps note type name → field names. The dialog writes the
fields in each note type's own order; hand-edit the JSON if you want a different
column order.

## Development

```
__init__.py     menu wiring, clipboard + CSV actions (thin Qt layer)
exporter.py     HTML→text, field resolution, TSV/CSV serialization (no Anki imports)
settings.py     the settings dialog
config.json     default config shipped with the add-on
config.md       help text shown in Anki's config editor
```

Tests:

```bash
make test                     # all three suites
python3 tests/test_exporter.py    # unit tests, any python3 — no Anki needed
make integration                  # uses Anki's bundled Python
```

`tests/test_with_anki.py` builds a throwaway collection in a temp directory and
checks parsing/CSV output against real note objects; `tests/test_gui_wiring.py`
drives the real Qt widgets headlessly to check the context menu, clipboard and
settings dialog. Neither touches a real collection. CI runs the unit suite only
(the others need an Anki installation).

Build the release file:

```bash
make release
# dist/anki_field_exporter.ankiaddon  -> upload to ankiweb.net/shared/addons
```

`make release` bumps `mod` in `manifest.json` (Anki's update check uses it) and
zips the shipped files only — tests, docs and your personal config are excluded.

## Publishing checklist

- [ ] Fill in `homepage` and `author` in `manifest.json`
- [ ] `make release`
- [ ] Upload `dist/anki_field_exporter.ankiaddon` at
      <https://ankiweb.net/shared/addons> (needs a free AnkiWeb account)
- [ ] After AnkiWeb assigns an ID, add `"ankiweb_id": <id>` to `manifest.json`
- [ ] Take a screenshot of the settings dialog for the AnkiWeb listing

## Licence

AGPL-3.0 — see [LICENSE](LICENSE). Same licence as Anki itself.
