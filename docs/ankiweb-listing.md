# AnkiWeb listing (ready to paste)

**Add-on name**

Field Exporter

**Description**

Export the fields you choose from selected cards in the Browser — to the
clipboard or a CSV file — with one right-click.

Tell it once which fields matter for each note type, then select any number of
cards, right-click, and pick:

- **Copy fields to clipboard** — tab-separated with a header row, ready to paste
  into Excel / Numbers / Google Sheets, a note, or a chat window.
- **Export fields to CSV…** — UTF-8 CSV (Excel-friendly) with a timestamped name.

Notes are exported once even when several of their cards are selected, HTML is
converted to clean plain text, and multi-line fields stay intact.

Settings are in a dialog (Tools → Field Exporter…): tick note types and fields,
choose what happens to note types you have not configured, and pick a default
CSV folder. Power users can still edit the JSON config.

Good for: pulling card content into notes, study documents, spreadsheets, or an
LLM; making backups of specific fields; sharing card content with people who do
not use Anki.

Requires Anki 2.1.50+ (desktop only — AnkiMobile and AnkiDroid cannot run
add-ons). No dependencies, nothing is uploaded anywhere.

**Tags**

export, csv, clipboard, copy, fields, browser, content, backup

**Support / source**

(put your GitHub URL here)

**Version notes — 1.0.0**

First release: per-note-type field selection with a settings dialog, copy as
TSV, save as CSV, plain-text conversion of field HTML.
