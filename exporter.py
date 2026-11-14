"""Export logic for the Field Exporter add-on.

This module intentionally imports nothing from Anki, so the parsing /
formatting logic can be unit-tested with a plain Python interpreter.
`collect_records` only duck-types the collection object it is given
(anything with a ``get_note(note_id)`` method works).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional, Sequence

CLIPBOARD_DELIMITER = "\t"
CSV_DELIMITER = ","
CSV_LINETERMINATOR = "\r\n"
CLIPBOARD_LINETERMINATOR = "\n"

UNCONFIGURED_ALL = "all_fields"
UNCONFIGURED_SKIP = "skip"

DEFAULTS: Dict[str, Any] = {
    # Which fields to export, per note type. Empty until the user configures
    # something (through the settings dialog or Anki's config editor), which
    # falls back to "export all fields" - see unconfigured_notetype.
    "notetype_fields": {},
    # "all_fields" -> export every field of that note type
    # "skip"       -> leave those notes out of the export
    "unconfigured_notetype": UNCONFIGURED_ALL,
    # Emit a header row (used by both CSV and clipboard output).
    "include_header_row": True,
    # Where the "Save as CSV" dialog starts. "" -> home folder.
    "csv_directory": "",
}


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------


def normalize_config(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge a stored config over the defaults and repair invalid values."""
    cfg: Dict[str, Any] = {
        "notetype_fields": {
            str(name): [str(f) for f in fields if str(f).strip()]
            for name, fields in DEFAULTS["notetype_fields"].items()
        },
        "unconfigured_notetype": DEFAULTS["unconfigured_notetype"],
        "include_header_row": DEFAULTS["include_header_row"],
        "csv_directory": DEFAULTS["csv_directory"],
    }
    if not isinstance(raw, dict):
        return cfg

    mapping = raw.get("notetype_fields")
    if isinstance(mapping, dict):
        cleaned: Dict[str, List[str]] = {}
        for name, fields in mapping.items():
            if not isinstance(name, str):
                continue
            if isinstance(fields, str):
                fields = [fields]
            if not isinstance(fields, (list, tuple)):
                continue
            cleaned[name] = [str(f).strip() for f in fields if str(f).strip()]
        cfg["notetype_fields"] = cleaned

    mode = raw.get("unconfigured_notetype")
    if isinstance(mode, str) and mode.strip().lower() in (
        UNCONFIGURED_ALL,
        UNCONFIGURED_SKIP,
    ):
        cfg["unconfigured_notetype"] = mode.strip().lower()

    if "include_header_row" in raw:
        cfg["include_header_row"] = bool(raw["include_header_row"])

    if isinstance(raw.get("csv_directory"), str):
        cfg["csv_directory"] = raw["csv_directory"]

    return cfg


def _lookup_configured(
    notetype_name: str, config: Dict[str, Any]
) -> Optional[List[str]]:
    """Fields configured for this note type, or None if it is not configured."""
    mapping = config.get("notetype_fields") or {}
    if notetype_name in mapping:
        return list(mapping[notetype_name])
    lowered = {str(key).lower(): value for key, value in mapping.items()}
    match = lowered.get(str(notetype_name).lower())
    if match is not None:
        return list(match)
    return None


def is_configured(notetype_name: str, config: Dict[str, Any]) -> bool:
    """True when the note type has an explicit entry in the config."""
    return _lookup_configured(notetype_name, config) is not None


def resolve_fields(
    notetype_name: str,
    available_fields: Sequence[str],
    config: Dict[str, Any],
) -> Optional[List[str]]:
    """Return the fields to export for `notetype_name`.

    ``None`` means "this note type is configured to be skipped".
    """
    configured = _lookup_configured(notetype_name, config)
    if configured is not None:
        return configured

    if config.get("unconfigured_notetype") == UNCONFIGURED_SKIP:
        return None
    return list(available_fields)


# --------------------------------------------------------------------------
# html -> plain text
# --------------------------------------------------------------------------

_SKIP_CONTENT = {"style", "script", "title", "head"}
_BREAK_ON_START = {"br", "hr"}
_LINE_BREAK_TAGS = {"br", "hr", "div", "p", "li", "ul", "ol", "tr", "table",
                    "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6",
                    "section", "article", "header", "footer", "dd", "dt"}
_CELL_TAGS = {"td", "th"}
_RAW_TAGS = {"pre"}

_WS_RE = re.compile(r"[ \t\f\v]+")
_MANY_NEWLINES_RE = re.compile(r"\n{3,}")


class _HTMLToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: List[str] = []
        self._skip_depth = 0
        self._raw_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in _SKIP_CONTENT:
            self._skip_depth += 1
        elif tag in _RAW_TAGS:
            self._raw_depth += 1
            self.chunks.append("\n")
        elif tag in _BREAK_ON_START:
            self.chunks.append("\n")
        elif tag == "img":
            src = dict(attrs).get("src")
            if src:
                self.chunks.append("[image: %s]" % src)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_CONTENT:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _RAW_TAGS:
            self._raw_depth = max(0, self._raw_depth - 1)
            self.chunks.append("\n")
        elif tag in _LINE_BREAK_TAGS:
            self.chunks.append("\n")
        elif tag in _CELL_TAGS:
            self.chunks.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if not self._raw_depth:
            # In HTML a raw newline is just whitespace.
            data = data.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        self.chunks.append(data)


def _tidy(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_WS_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = _MANY_NEWLINES_RE.sub("\n\n", "\n".join(lines))
    return text.strip()


def html_to_text(value: Optional[str]) -> str:
    """Strip HTML from an Anki field, keeping one line per visual line."""
    if not value:
        return ""
    if "<" not in value and "&" not in value:
        return value.strip()

    parser = _HTMLToText()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        return value.strip()
    return _tidy("".join(parser.chunks))


# --------------------------------------------------------------------------
# collecting notes
# --------------------------------------------------------------------------


@dataclass
class Record:
    note_id: int
    notetype: str
    values: Dict[str, str]


@dataclass
class ExportResult:
    records: List[Record] = field(default_factory=list)
    # Note types left out because unconfigured_notetype == "skip".
    skipped_notetypes: List[str] = field(default_factory=list)
    # Note types exported with *all* their fields because the user never
    # configured them. Handy for pointing people at the settings dialog.
    unconfigured_notetypes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _note_field_values(note: Any) -> Dict[str, str]:
    """Map ``field name -> raw value`` for an Anki note object."""
    notetype = note.note_type() or {}
    names = [f.get("name", "") for f in notetype.get("flds", [])]
    values = list(getattr(note, "fields", []) or [])
    out: Dict[str, str] = {}
    for index, name in enumerate(names):
        if not name:
            continue
        out[name] = values[index] if index < len(values) else ""
    return out


def collect_records(
    col: Any,
    note_ids: Iterable[int],
    config: Optional[Dict[str, Any]] = None,
) -> ExportResult:
    """Read the selected notes and return one record per note.

    Notes with the same id are collapsed (a note with several selected cards
    is exported once). Order of `note_ids` is preserved.
    """
    cfg = normalize_config(config)
    result = ExportResult()
    seen = set()

    for note_id in note_ids:
        if note_id in seen:
            continue
        seen.add(note_id)

        try:
            note = col.get_note(note_id)
        except Exception as exc:  # missing / deleted note
            result.errors.append("note %s: %s" % (note_id, exc))
            continue

        notetype = note.note_type() or {}
        notetype_name = notetype.get("name") or "Unknown"
        available = [f.get("name", "") for f in notetype.get("flds", [])]
        wanted = resolve_fields(notetype_name, available, cfg)
        if wanted is None:
            if notetype_name not in result.skipped_notetypes:
                result.skipped_notetypes.append(notetype_name)
            continue

        if not is_configured(notetype_name, cfg):
            if notetype_name not in result.unconfigured_notetypes:
                result.unconfigured_notetypes.append(notetype_name)

        raw_values = _note_field_values(note)
        values = {name: html_to_text(raw_values.get(name, "")) for name in wanted}
        result.records.append(Record(note_id, notetype_name, values))

    return result


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------


def build_table(
    records: Sequence[Record],
) -> "tuple[List[str], List[List[str]]]":
    """Column header (union of exported fields, first-seen order) + rows."""
    header: List[str] = []
    for record in records:
        for name in record.values:
            if name not in header:
                header.append(name)
    rows = [[record.values.get(name, "") for name in header] for record in records]
    return header, rows


def to_delimited(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    delimiter: str,
    include_header: bool,
    lineterminator: str,
) -> str:
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=delimiter,
        lineterminator=lineterminator,
        quoting=csv.QUOTE_MINIMAL,
    )
    if include_header:
        writer.writerow(list(header))
    for row in rows:
        writer.writerow(list(row))
    return buffer.getvalue()


def to_clipboard_text(
    records: Sequence[Record],
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """Tab-separated text (pastes cleanly into spreadsheets and editors)."""
    cfg = normalize_config(config)
    header, rows = build_table(records)
    return to_delimited(
        header,
        rows,
        CLIPBOARD_DELIMITER,
        cfg["include_header_row"],
        CLIPBOARD_LINETERMINATOR,
    )


def to_csv_text(
    records: Sequence[Record],
    config: Optional[Dict[str, Any]] = None,
) -> str:
    cfg = normalize_config(config)
    header, rows = build_table(records)
    return to_delimited(
        header,
        rows,
        CSV_DELIMITER,
        cfg["include_header_row"],
        CSV_LINETERMINATOR,
    )
