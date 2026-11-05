# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Tally XML exports (#34001): read a Tally masters export, count its parts, and turn ledgers and
stock items into rows the #34000 Tally presets match, so start_import_session opens their sessions
the same way it does for a spreadsheet. Ledger groups are counted, not imported: a ledger under
Sundry Debtors or Sundry Creditors, at any depth, is a party. Stock groups are imported as Item
Groups, each under its parent. This module writes nothing.

The file is streamed with lxml, entities and DTDs off and no network, so an export of any size
is read one record at a time and nothing outside the file is ever read.
"""

import inspect
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from frappe import _
from lxml import etree

from frappe_assistant_core.utils.import_presets import MAX_PRESET_ROWS, Sheet, _number, _plain
from frappe_assistant_core.utils.import_session import FileProblem, check_size

PARTS = {"LEDGER": "ledgers", "STOCKITEM": "stock_items", "STOCKGROUP": "stock_groups", "GROUP": "groups"}
IMPORTABLE = {
    "ledgers": "tally_prime.ledgers",
    "stock_items": "tally_prime.stock_items",
    "stock_groups": "tally_prime.stock_groups",
}
# Tally's reserved groups whose ledgers, and the ledgers of the groups under them, are parties
PARTY_GROUPS = ("Sundry Debtors", "Sundry Creditors")
ROOT = "Primary"  # Tally's top of every tree, written "&#4; Primary"
SAMPLE = 10
MAX_LISTED = 50  # entries of a count table in the listing reply
MAX_NAMED = 10  # tags named in the vouchers-only refusal

NOT_TALLY = (
    "This XML is not a Tally export. Export it from Tally as XML (Masters), or as Excel, and upload that."
)
NO_MASTERS = (
    "This Tally export has no ledgers, groups or stock items (it holds: {0}). "
    "Export the masters: Alt+E > Masters."
)

# Column -> where to read it, first present and not blank. "@X" is an attribute, "A/B" a child path.
COLUMNS = {
    "ledgers": [
        ("Name", ["@NAME", "LANGUAGENAME.LIST/NAME.LIST/NAME"]),
        ("Parent", ["PARENT"]),
        ("GSTIN/UIN", ["LEDGSTREGDETAILS.LIST/GSTIN", "PARTYGSTIN", "GSTIN"]),
        ("E-mail", ["EMAIL"]),
        ("Ledger Mobile", ["LEDGERMOBILE", "LEDGERPHONE"]),
        ("PAN", ["INCOMETAXNUMBER"]),
        ("State", ["LEDMAILINGDETAILS.LIST/STATE", "LEDSTATENAME", "STATENAME"]),
        ("Mailing Name", ["LEDMAILINGDETAILS.LIST/MAILINGNAME", "MAILINGNAME.LIST/MAILINGNAME"]),
        ("Opening Balance", ["OPENINGBALANCE"]),
    ],
    "stock_items": [
        ("Name", ["@NAME", "LANGUAGENAME.LIST/NAME.LIST/NAME"]),
        ("Stock Group", ["PARENT"]),
        ("Base Units", ["BASEUNITS"]),
        ("HSN Code", ["HSNDETAILS.LIST/HSNCODE", "GSTDETAILS.LIST/HSNCODE", "HSNCODE"]),
        ("Description", ["DESCRIPTION"]),
        ("Category", ["CATEGORY"]),
        ("Opening Quantity", ["OPENINGBALANCE"]),
        ("Opening Rate", ["OPENINGRATE"]),
    ],
    "stock_groups": [
        ("Stock Group Name", ["@NAME", "LANGUAGENAME.LIST/NAME.LIST/NAME"]),
        ("Under Stock Group", ["PARENT"]),
        ("Quantities Added", ["ISADDABLE"]),
    ],
}
FLIP_SIGN = {
    "Opening Balance"
}  # Tally XML writes a debit balance as negative; the presets read Dr as positive
TAGS = {part: tag for tag, part in PARTS.items()}
LABELS = {
    "ledgers": "ledgers",
    "stock_items": "stock items",
    "stock_groups": "stock groups",
    "groups": "groups",
}

# every control character but tab, newline, return: C0, DEL and C1
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]+")


@dataclass
class Part:
    part: str
    count: int = 0
    sample: List[str] = field(default_factory=list)
    by_parent: Counter = field(default_factory=Counter)


@dataclass
class Survey:
    company: Optional[str]
    parts: Dict[str, Part]
    other_records: Dict[str, int]


def capped(counter: Counter, limit: int = MAX_LISTED) -> Dict[str, int]:
    """The ``limit`` biggest entries (ties in first-seen order), a blank key shown as (none). When
    more were left out, one more entry "(N more)" holds the records under them."""
    ranked = counter.most_common()
    shown = {(key or "(none)"): count for key, count in ranked[:limit]}
    rest = ranked[limit:]
    if rest:
        shown[_("({0} more)").format(len(rest))] = sum(count for _key, count in rest)
    return shown


def is_xml(file_doc) -> bool:
    return (file_doc.get_extension()[1] or "").lstrip(".").lower() == "xml"


def _content(file_doc) -> bytes:
    if not is_xml(file_doc):
        raise FileProblem(_("Only a Tally .xml export can be read here."))
    check_size(file_doc)
    # The bytes as written: Frappe v16's get_content() decodes a file read from disk with the
    # first encoding that doesn't fail, and Tally's UTF-16 passes as windows-1250 with its BOM
    # lost, so lxml found no ENVELOPE. encodings=() keeps them; v15 has no such argument and keeps
    # bytes that aren't UTF-8 as they are.
    raw = {"encodings": ()} if "encodings" in inspect.signature(file_doc.get_content).parameters else {}
    content = file_doc.get_content(**raw)
    return content.encode("utf-8") if isinstance(content, str) else content


def _local(tag: Any) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _text(value: Optional[str]) -> str:
    return " ".join(_CONTROL.sub("", value or "").split())


def _value(element, path: str) -> str:
    if path.startswith("@"):
        return _text(element.get(path[1:]))
    nodes = [element]
    for step in path.split("/"):
        nodes = [child for node in nodes for child in node if _local(child.tag) == step]
        if not nodes:
            return ""
    for node in nodes:
        text = _text("".join(node.itertext()))
        if text:
            return text
    return ""


# A Tally masters export of 10,000 ledgers has about 300,000 elements; a file of far more is not one.
MAX_ELEMENTS = 2_000_000
# A record is held whole until it ends; a ledger or stock item has a few hundred elements.
MAX_RECORD_ELEMENTS = 100_000


def _walk(content: bytes, company: List[str]) -> Iterator[Tuple[str, Any]]:
    """(tag, element) for every child of a TALLYMESSAGE, one at a time. The company name, when
    the export carries one, is appended to ``company``."""
    events = etree.iterparse(
        io.BytesIO(content),
        events=("start", "end"),
        recover=True,
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
    )
    started, in_message, elements = False, 0, 0
    in_record = None  # the elements read into the record being read, None between records
    try:
        for event, element in events:
            name = _local(element.tag)
            parent = element.getparent()
            in_a_message = parent is not None and _local(parent.tag) == "TALLYMESSAGE"
            if event == "start":
                elements += 1
                if elements > MAX_ELEMENTS:
                    raise FileProblem(
                        _("The XML has more than {0} elements, more than a Tally masters export has.").format(
                            MAX_ELEMENTS
                        )
                    )
                if not started:
                    started = True
                    if name != "ENVELOPE":
                        raise FileProblem(_(NOT_TALLY))
                in_message += name == "TALLYMESSAGE"
                if in_a_message:
                    in_record = 0
                elif in_record is not None:
                    in_record += 1
                    if in_record > MAX_RECORD_ELEMENTS:
                        raise FileProblem(
                            _(
                                "A record in the XML has more than {0} elements, more than a Tally master has."
                            ).format(MAX_RECORD_ELEMENTS)
                        )
                continue
            if name == "SVCURRENTCOMPANY" and not company and _text(element.text):
                company.append(_text(element.text))
            # A message nested in a message counts itself out too (#34438)
            in_message -= name == "TALLYMESSAGE"
            if in_a_message:
                in_record = None
                yield name, element
                element.clear()
            elif name == "TALLYMESSAGE" or not in_message:
                # Nothing reads a finished element again: outside a message too, so a file of
                # other elements isn't held in memory whole (#34438).
                element.clear()
                while element.getprevious() is not None:
                    del element.getparent()[0]
    except FileProblem:
        raise
    except etree.LxmlError as e:
        raise FileProblem(_("Could not read the XML: {0}").format(str(e)))
    if not started:
        raise FileProblem(_(NOT_TALLY))


def survey(file_doc) -> Survey:
    """Every part of the export, counted, with up to 10 names each and the parents of ledgers
    and groups. Raises FileProblem when the file is not a Tally masters export."""
    return read(file_doc)[0]


def part_sheet(file_doc, part: str) -> Sheet:
    """One importable part as a Sheet: a header row the part's Tally preset matches, then one row
    per record."""
    sheet = read(file_doc, [part])[1][part]
    if isinstance(sheet, FileProblem):
        raise sheet
    return sheet


def read(file_doc, wanted: Iterable[str] = ()) -> Tuple[Survey, Dict[str, Any]]:
    """The survey, and the sheet of each ``wanted`` part read in the same pass, so a file of up to
    the site's size limit is parsed once (#34438). A part too large to import has its FileProblem
    in place of its sheet. Raises FileProblem when the file is not a Tally masters export."""
    company: List[str] = []
    parts: Dict[str, Part] = {}
    other: Counter = Counter()
    rows = {part: [[column for column, _paths in COLUMNS[part]]] for part in wanted if part in COLUMNS}
    too_large: Dict[str, FileProblem] = {}
    group_parents: Dict[str, str] = {}
    for tag, element in _walk(_content(file_doc), company):
        part = PARTS.get(tag)
        if not part:
            other[tag] += 1
            continue
        found = parts.setdefault(part, Part(part))
        found.count += 1
        name = _value(element, "@NAME") or _value(element, "LANGUAGENAME.LIST/NAME.LIST/NAME")
        if name and len(found.sample) < SAMPLE:
            found.sample.append(name)
        if part in ("ledgers", "groups"):
            found.by_parent[_value(element, "PARENT")] += 1
        if part == "groups" and name:
            group_parents[name] = _value(element, "PARENT")
        if part not in rows or part in too_large:
            continue
        # The limit counts records, not the header: exactly MAX_PRESET_ROWS records are allowed and
        # the next one is refused (rows holds the header plus the records read so far).
        if len(rows[part]) > MAX_PRESET_ROWS:
            too_large[part] = FileProblem(
                _("This export has more than {0:,} {1}. Export them from Tally in parts.").format(
                    MAX_PRESET_ROWS, LABELS[part]
                )
            )
            continue
        rows[part].append(_row(part, element))
    if not parts:
        if other:
            ranked = other.most_common()
            held = ", ".join(f"{tag} {count}" for tag, count in ranked[:MAX_NAMED])
            if len(ranked) > MAX_NAMED:
                held += " " + _("and {0} more").format(len(ranked) - MAX_NAMED)
            raise FileProblem(_(NO_MASTERS).format(held))
        raise FileProblem(_(NOT_TALLY))
    if "ledgers" in rows:
        _route_sub_groups(rows["ledgers"], group_parents)
    for row in rows.get("stock_groups", [])[1:]:
        if row[1] == ROOT:
            row[1] = ""  # a top stock group: ERPNext puts it under its own root
    sheets = {
        part: too_large.get(part) or Sheet(f"{part} (Tally XML)", part_rows)
        for part, part_rows in rows.items()
    }
    return Survey(company[0] if company else None, parts, dict(other)), sheets


def _route_sub_groups(rows: List[List[str]], group_parents: Dict[str, str]) -> None:
    """A ledger in a group under Sundry Debtors or Sundry Creditors ("Local Debtors") is a party
    too: its group column says the reserved group it is under, which the ledgers preset routes
    by. The export lists every group with its parent, before or after the ledgers. Each group is
    walked up once, so a long or looping chain costs no more than the groups in it."""
    at = [column for column, _paths in COLUMNS["ledgers"]].index("Parent")
    party: Dict[str, str] = {name: name for name in PARTY_GROUPS}  # group -> its reserved group, or ""
    for row in rows[1:]:
        group, chain, seen = row[at], [], set()
        while group and group not in party and group not in seen:
            chain.append(group)
            seen.add(group)
            group = group_parents.get(group, "")
        found = party.get(group, "") if group else ""
        for name in chain:
            party[name] = found
        if found:
            row[at] = found


def _row(part: str, element) -> List[str]:
    """A record as a row of its part's columns."""
    row = []
    for column, paths in COLUMNS[part]:
        value = next((v for v in (_value(element, path) for path in paths) if v), "")
        if column in FLIP_SIGN and value:
            number = _number(value)
            # Hostile values (1E999999999, NaN, Infinity) are kept as written, never expanded.
            if number is not None and number.is_finite() and abs(number.adjusted()) < 30:
                value = _plain(-number)
        row.append(value)
    return row


def parts_problem(parts: List[str], found: Survey) -> Optional[str]:
    """Why these parts can't be imported from this export, or None."""
    if not parts:
        return _("Give at least one part to import: {0}.").format(", ".join(IMPORTABLE))
    for part in parts:
        if part == "groups":
            return _("Tally groups are listed but not imported.")
        if part not in IMPORTABLE:
            return _("No part '{0}'. Importable parts: {1}.").format(part, ", ".join(IMPORTABLE))
        if part not in found.parts:
            return _("This export has no {0}.").format(LABELS[part])
    return None
