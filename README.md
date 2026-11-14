# Field Exporter for Anki

[![Anki 2.1.50+](https://img.shields.io/badge/Anki-2.1.50%2B-blue)](https://apps.ankiweb.net)
[![Licence: AGPL-3.0](https://img.shields.io/badge/licence-AGPL--3.0-green)](LICENSE)
[![tests](https://img.shields.io/github/actions/workflow/status/dyzur/Anki-Field-Exporter-Addon/tests.yml?label=tests)](https://github.com/dyzur/Anki-Field-Exporter-Addon/actions/workflows/tests.yml)
[![AnkiWeb](https://img.shields.io/badge/AnkiWeb-1114764677-orange)](https://ankiweb.net/shared/info/1114764677)

![Field Exporter settings dialog](docs/images/settings-dialog.png)

IMPORTANT: This was made 100% by AI. 

Right-click any selection in Anki's **Browser** and either copy the fields you
care about to the clipboard, or save them as a `.csv`. Which fields get exported
is set once per note type, pick them in a dialog, no JSON needed.

Built for people who reuse their card content elsewhere: pasting into notes,
docs, spreadsheets, or an LLM.

## Usage

1. **Tools → Field Exporter…** → tick the fields you want for each note type
   (use the filter box if you have many) → **Save**.
2. In the Browser, select the notes you want and **right-click**:

![Right-click menu in the Browser](docs/images/browser-menu.png)

```
────────────────────────────
Copy fields to clipboard (12 notes)
Export fields to CSV… (12 notes)
────────────────────────────
Field Exporter settings…
```

- **Copy fields to clipboard** - tab-separated text with a header row; paste
  straight into Excel, Numbers, Google Sheets, or a text field.
- **Export fields to CSV…** - save dialog with a timestamped default name.
  Written as UTF-8 with BOM so Excel and Numbers show accented characters
  correctly.
- Both entries grey out when nothing is selected, and the count is the number of
  *notes* - a note with several selected cards is exported once.

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

**From AnkiWeb:** Tools → Add-ons → Get Add-ons… → paste `1114764677`, or open
<https://ankiweb.net/shared/info/1114764677> and click *Download*.

**Manual:** download the latest `.ankiaddon` from
[releases](https://github.com/dyzur/Anki-Field-Exporter-Addon/releases) and use
Tools → Add-ons → Install from file…

Restart Anki afterwards. Settings survive updates.

Requires Anki 2.1.50 or newer (desktop). Not compatible with AnkiMobile or
AnkiDroid — they cannot run add-ons.

## Configuration

Everything can be set in the dialog — that is the recommended way. The same
settings are reachable as JSON via **Tools → Add-ons → Field Exporter → Config**
(see also `config.md`). Anki stores what you save in the add-on's `meta.json`;
the `config.json` shipped with the add-on is the starting default:

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
fields in each note type's own order; edit the JSON if you want a different
column order.

## Problems, ideas, bugs

Open an issue: <https://github.com/dyzur/Anki-Field-Exporter-Addon/issues>. If
you hit an error, Anki shows a traceback box — paste the whole thing, plus your
Anki version (Help → About).

## Licence

AGPL-3.0 — see [LICENSE](LICENSE). Same licence as Anki itself.

Building from source, running the tests and cutting a release are described in
[docs/MAINTAINING.md](docs/MAINTAINING.md).
