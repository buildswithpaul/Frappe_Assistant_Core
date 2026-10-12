# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Which DocType fields each group on the FAC Admin Settings tab shows.

A *unit* is the fieldname of the nearest preceding Tab Break or Section Break.
Groups list units, so a field added to a section shows up without a page change.
"""

import json
import os

import frappe

SETTINGS_MAP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "assistant_core",
    "page",
    "fac_admin",
    "settings_groups.json",
)
BREAKS = ("Section Break", "Tab Break")
LAYOUT = (*BREAKS, "Column Break")


def load_settings_map(path: str | None = None) -> dict:
    # `path` is a module constant or a test fixture — never request data.
    with open(path or SETTINGS_MAP_PATH) as fh:  # nosemgrep: frappe-security-file-traversal
        return json.load(fh)


def units_of(fields: list) -> dict[str, list]:
    units: dict[str, list] = {}
    current = ""
    for df in fields:
        if df.fieldtype in BREAKS:
            current = df.fieldname
        units.setdefault(current, []).append(df)
    return units


def _is_shown(df, skip_fields: set) -> bool:
    return not (df.hidden or df.fieldtype == "Password" or df.fieldname in skip_fields)


def resolve_groups(settings_map: dict) -> list[dict]:
    skip_fields = set(settings_map.get("skip_fields", []))
    groups = []
    for group in settings_map["groups"]:
        units = units_of(frappe.get_meta(group["doctype"]).fields)
        fields = [
            df.fieldname
            for unit in group["units"]
            for df in units.get(unit, [])
            if df.fieldtype in LAYOUT or _is_shown(df, skip_fields)
        ]
        groups.append(
            {
                "key": group["key"],
                "label": group["label"],
                "icon": group.get("icon"),
                "doctype": group["doctype"],
                "read_only": bool(group.get("read_only")),
                "fields": fields,
            }
        )
    return groups


def _mapped_units(settings_map: dict) -> dict[str, set]:
    mapped: dict[str, set] = {}
    for group in settings_map["groups"]:
        mapped.setdefault(group["doctype"], set()).update(group["units"])
    for doctype, units in settings_map.get("skip_units", {}).items():
        mapped.setdefault(doctype, set()).update(units)
    return mapped


def unmapped_units(settings_map: dict) -> dict[str, list[str]]:
    """Units that own a field the page would show but that no group or skip list names."""
    skip_fields = set(settings_map.get("skip_fields", []))
    missing: dict[str, list[str]] = {}
    for doctype, mapped in _mapped_units(settings_map).items():
        for unit, fields in units_of(frappe.get_meta(doctype).fields).items():
            if unit in mapped:
                continue
            if any(df.fieldtype not in LAYOUT and _is_shown(df, skip_fields) for df in fields):
                missing.setdefault(doctype, []).append(unit)
    return missing


def missing_names(settings_map: dict) -> list[str]:
    """Units and skipped fields named in the map that their DocType does not have."""
    missing = []
    for doctype, mapped in _mapped_units(settings_map).items():
        existing = {df.fieldname for df in frappe.get_meta(doctype).fields}
        missing += [f"{doctype}.{unit}" for unit in sorted(mapped) if unit not in existing]
    doctypes = {g["doctype"] for g in settings_map["groups"]}
    all_fields = {df.fieldname for doctype in doctypes for df in frappe.get_meta(doctype).fields}
    missing += [
        f"skip_fields.{name}" for name in settings_map.get("skip_fields", []) if name not in all_fields
    ]
    return missing


@frappe.whitelist(methods=["GET"])
def get_settings_groups() -> dict:
    """The FAC Admin Settings tab's groups, each with the fieldnames it renders."""
    frappe.only_for(["System Manager", "Assistant Admin"])
    return {"groups": resolve_groups(load_settings_map())}
