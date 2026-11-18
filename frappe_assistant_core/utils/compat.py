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

"""Where FAC meets a difference between Frappe / ERPNext 15 and 16, and India Compliance being there or not.

New code asks here instead of reading ``frappe.__version__`` inline. A helper is added when a story
needs one, with a test on both versions.
"""

from typing import Any, Dict, Optional

import frappe

# Keys of a chart node that describe the account, not a child account. v15 lists the first seven
# in create_charts; v16 reads them from get_chart_metadata_fields(), which adds account_category.
CHART_NODE_KEYS = frozenset(
    {
        "account_name",
        "account_number",
        "account_type",
        "root_type",
        "is_group",
        "tax_rate",
        "account_currency",
        "account_category",
    }
)


def _major(version: Optional[str]) -> Optional[int]:
    """The major number of a version string such as ``16.52.0``, or None when there is none."""
    try:
        return int(str(version).split(".")[0])
    except (TypeError, ValueError):
        return None


def frappe_major() -> int:
    """15 or 16: the Frappe major version this site runs."""
    return _major(frappe.__version__) or 0


def erpnext_major() -> Optional[int]:
    """The ERPNext major version, or None when ERPNext is not installed."""
    if "erpnext" not in frappe.get_installed_apps():
        return None
    import erpnext

    return _major(erpnext.__version__)


def has_india_compliance() -> bool:
    """Whether India Compliance is installed on this site."""
    return "india_compliance" in frappe.get_installed_apps()


def has_field(doctype: str, fieldname: str) -> bool:
    """Whether ``doctype`` has ``fieldname`` on this site (custom fields and other apps count).
    Frappe caches the meta, so this is cheap to ask repeatedly."""
    return bool(frappe.get_meta(doctype).has_field(fieldname))


def prepare_chart(forest: Dict[str, Any], currency: str) -> Dict[str, Any]:
    """A chart for ERPNext's ``create_charts(custom_chart=..., from_coa_importer=True)``, the same
    on both versions: every account node carries ``account_name`` (that call reads it from the node,
    not from the key) and ``account_currency`` (v16 doesn't fall back to the company currency for a
    custom chart; v15 does). The chart passed in is not changed.
    """

    def fill(children: Dict[str, Any]) -> Dict[str, Any]:
        filled = {}
        for key, child in children.items():
            if key in CHART_NODE_KEYS or not isinstance(child, dict):
                filled[key] = child
                continue
            node = fill(child)
            node.setdefault("account_name", key)
            node.setdefault("account_currency", currency)
            filled[key] = node
        return filled

    return fill(forest)


def create_charts(company: str, forest: Dict[str, Any]) -> None:
    """Create ``company``'s accounts from ``forest`` through ERPNext's own chart code, on v15 and v16.

    ERPNext inserts the accounts with ``ignore_permissions``: the caller checks that the user may
    create accounts for the company first.
    """
    from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import create_charts as erp

    currency = frappe.get_cached_value("Company", company, "default_currency")
    erp(company, custom_chart=prepare_chart(forest, currency), from_coa_importer=True)
