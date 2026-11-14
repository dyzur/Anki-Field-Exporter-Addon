## Picking the fields

The easy way is the dialog: **Tools → Field Exporter…**, or right-click a
selection in the Browser and pick *Field Exporter settings…*. Tick the fields
you want for each note type, then press **Save**.

The same settings can be edited as JSON here, or from **Tools → Add-ons →
Field Exporter → Config**. Column order in the export follows the order of each
note type's fields. Field names must match the note type exactly.

```json
{
  "notetype_fields": {
    "Basic": ["Front", "Back"],
    "Cloze": ["Text"]
  },
  "unconfigured_notetype": "all_fields",
  "include_header_row": true,
  "csv_directory": ""
}
```

| Key | Meaning |
| --- | --- |
| `notetype_fields` | Note type name → list of field names to export. Empty means nothing has been chosen yet. |
| `unconfigured_notetype` | Note types missing from the list: `"all_fields"` exports every field of theirs, `"skip"` leaves those notes out. |
| `include_header_row` | Emit a header row with the field names (applies to both outputs). |
| `csv_directory` | Folder the “Save as CSV” dialog starts in. Empty = your home folder. |

Note type names are matched case-insensitively. A field that is listed here but
missing on a note is exported as an empty cell.
