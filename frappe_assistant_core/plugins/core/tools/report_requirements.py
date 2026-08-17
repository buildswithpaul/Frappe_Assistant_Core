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

"""
Report Requirements Tool for Core Plugin.
Understand report requirements, structure, and metadata before execution.
"""

import re
from typing import Any, Dict

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool

# Fieldtypes whose `options` is a set of accepted values rather than a target
# DocType. Everything else (Link, MultiSelectList) points at a DocType instead.
VALUE_CONSTRAINED_FIELDTYPES = {"Select", "Autocomplete"}

# A JavaScript string literal in each of its three quotings. Empty strings have
# to match as well: a leading "" in an options array — the "no selection" entry —
# threw naive quote-pairing off by one, so the separators between values were
# captured instead of the values themselves (issue #229).
_JS_STRING_LITERAL = re.compile(r'"((?:[^"\\]|\\.)*)"' r"|'((?:[^'\\]|\\.)*)'" r"|`((?:[^`\\]|\\.)*)`")


def _extract_js_string_literals(text: str) -> list:
    """Every string literal in a fragment of JavaScript, in source order."""
    return [
        next((group for group in match.groups() if group is not None), "")
        for match in _JS_STRING_LITERAL.finditer(text)
    ]


def normalize_filter_options(filter_def: Dict[str, Any]) -> Dict[str, Any]:
    """Express a value-constrained filter's accepted values as an explicit list.

    Report JS declares Select options three ways: an array of strings, an array
    of ``{value, label}`` objects, and a newline-delimited string. Only the first
    two arrived as a list — the third reached callers as an opaque
    ``"Monthly\\nQuarterly"``, so the same contract had two shapes and a
    constrained value set could not be read off the advertised definition
    (issue #229).

    Mutates and returns the filter definition.
    """
    if filter_def.get("fieldtype") not in VALUE_CONSTRAINED_FIELDTYPES:
        return filter_def

    options = filter_def.get("options")
    if isinstance(options, str):
        # Read from a .js file, so an escaped newline arrives as a literal
        # backslash-n; a child-table row carries a real newline.
        filter_def["options"] = [value.strip() for value in re.split(r"\\n|\n", options) if value.strip()]
    elif isinstance(options, (list, tuple)):
        filter_def["options"] = [str(value).strip() for value in options if str(value).strip()]

    return filter_def


def discover_filter_definitions(report_doc) -> Dict[str, Dict[str, Any]]:
    """The report's filter contract as ``{fieldname: definition}``.

    The single entry point shared by ``report_requirements``, which advertises the
    contract, and ``generate_report``, which validates against it. Deriving both
    from here is what stops the two tools disagreeing about their own contract.
    """
    tool = ReportRequirements()
    parsed, _diagnostics = tool._discover_report_filters(report_doc.name, report_doc)
    return {
        filter_def["fieldname"]: filter_def
        for filter_def in (parsed or {}).get("filters", [])
        if filter_def.get("fieldname")
    }


class ReportRequirements(BaseTool):
    """
    Tool for analyzing report requirements, structure, and metadata.

    Provides capabilities for:
    - Required filter discovery
    - Column structure analysis
    - Report metadata and configuration
    - Filter guidance for complex reports
    - Error prevention for report execution
    """

    def __init__(self):
        super().__init__()
        self.name = "report_requirements"
        self.description = "Get report metadata including required and optional filters, columns, and execution requirements for Script Reports, Query Reports, and Custom Reports. Use this tool before executing reports to understand what filters are mandatory, what exact filter values are valid, and how to structure the report request. This prevents filter errors and helps plan successful report execution. Returns complete report metadata including filter definitions with field types (Link, Select, Date), valid enum options for select fields, column structure, report type, and capabilities. For a value-constrained filter (Select, Autocomplete) 'options' is an explicit list of accepted values, and every 'default' returned here is guaranteed to be accepted by generate_report. Filter contracts are per-report: the same filter name can mean different things in different reports (e.g. 'range' is an ageing bucket string like '30, 60, 90, 120' on the AR/AP reports but a periodicity Select elsewhere), so never reuse a value across reports. IMPORTANT: Use this FIRST before calling generate_report to understand what exact filter values are needed - Link fields require exact database names (e.g., exact Company name, Customer name), Select fields show valid enum values. Essential when generate_report returns filter errors or when planning complex report execution. Check 'filter_discovery_status': 'no_filters_declared' means the report genuinely takes no filters, while 'unresolved' means discovery failed and 'discovery_diagnostics' explains why. NOTE: Report Builder reports store a saved column/filter configuration rather than a filter contract and are not yet fully supported."
        self.requires_permission = None  # Permission checked dynamically per report

        self.inputSchema = {
            "type": "object",
            "properties": {
                "report_name": {
                    "type": "string",
                    "description": "Exact name of the Frappe report to analyze (e.g., 'Sales Analytics', 'Accounts Receivable Summary'). This helps understand available fields, required filters, valid filter options, and report structure before execution.",
                },
                "include_metadata": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether to include technical metadata (creation date, owner, SQL query, etc.) - useful for developers and administrators.",
                },
                "include_columns": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include column structure information.",
                },
                "include_filters": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include filter requirements and guidance.",
                },
            },
            "required": ["report_name"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute report requirements analysis"""
        report_name = arguments.get("report_name")
        include_metadata = arguments.get("include_metadata", False)
        include_columns = arguments.get("include_columns", True)
        include_filters = arguments.get("include_filters", True)

        try:
            # Import the report implementation for column analysis
            from .report_tools import ReportTools

            # Get basic column and filter info from existing implementation
            column_result = ReportTools.get_report_columns(report_name)

            if not column_result.get("success", False):
                return column_result

            # Get report document for prepared report info
            report_doc = frappe.get_doc("Report", report_name)

            # Start building comprehensive response
            result = {
                "success": True,
                "report_name": report_name,
                "report_type": column_result.get("report_type"),
                "prepared_report": getattr(report_doc, "prepared_report", False),
                "disable_prepared_report": getattr(report_doc, "disable_prepared_report", False),
            }

            # Add prepared report guidance
            if getattr(report_doc, "prepared_report", False) and not getattr(
                report_doc, "disable_prepared_report", False
            ):
                report_timeout = frappe.get_value("Report", report_name, "timeout") or 120
                result["prepared_report_info"] = {
                    "requires_background_processing": True,
                    "typical_execution_time": f"{report_timeout // 60} minutes for large datasets",
                    "behavior": "First execution automatically waits for completion (up to 5 minutes). Subsequent calls with same filters retrieve cached results instantly.",
                    "recommendation": "The tool will automatically wait for report completion. If timeout occurs, retry with the same filters to retrieve cached results.",
                }
            else:
                result["prepared_report_info"] = {
                    "requires_background_processing": False,
                    "behavior": "Direct execution - returns results immediately.",
                }

            # Add columns if requested
            if include_columns:
                result["columns"] = column_result.get("columns", [])

            # Add filter guidance if requested
            if include_filters:
                if "filter_guidance" in column_result:
                    result["filter_guidance"] = column_result["filter_guidance"]

                # Add filter requirements analysis
                result["filter_requirements"] = self._analyze_filter_requirements(
                    report_name, column_result.get("report_type")
                )

                # Discovery runs for every report type. Gating it to Script
                # Reports left Query and Custom Reports with no filter
                # definitions AND no discovery_diagnostics key, which is
                # indistinguishable from a report that genuinely takes none
                # (issue #223).
                parsed_filters, diagnostics = self._discover_report_filters(report_name, report_doc)
                result["discovery_diagnostics"] = diagnostics
                result["filter_discovery_status"] = diagnostics.get("status", "unresolved")

                if parsed_filters and parsed_filters.get("filters"):
                    result["filters_definition"] = parsed_filters["filters"]
                    result["required_filter_names"] = parsed_filters.get("required_filters", [])
                    result["conditional_required_filter_names"] = parsed_filters.get(
                        "conditional_required_filters", []
                    )
                    result["optional_filter_names"] = parsed_filters.get("optional_filters", [])

                    # Override filter_requirements with parsed data instead of pattern-based guesses
                    result["filter_requirements"] = self._build_requirements_from_parsed_filters(
                        parsed_filters
                    )
                elif diagnostics.get("status") == "no_filters_declared":
                    result["filters_definition"] = []
                    result["required_filter_names"] = []
                    result["optional_filter_names"] = []
                    result["filter_requirements"] = {
                        "common_required_filters": [],
                        "common_optional_filters": [],
                        "guidance": ["This report declares no filters and can be run without any."],
                    }

            # Add comprehensive metadata if requested
            if include_metadata:
                metadata = self._get_comprehensive_metadata(report_name)
                if metadata:
                    result["metadata"] = metadata

            return result

        except Exception as e:
            frappe.log_error(
                title=_("Report Requirements Error"), message=f"Error analyzing report requirements: {str(e)}"
            )

            return {"success": False, "error": str(e)}

    def _build_requirements_from_parsed_filters(self, parsed_filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build filter requirements from parsed filter definitions.

        Args:
            parsed_filters: Dictionary with 'filters', 'required_filters', 'optional_filters'

        Returns:
            Dictionary with human-readable filter requirements and guidance
        """
        requirements = {
            "common_required_filters": [],
            "conditional_required_filters": [],
            "common_optional_filters": [],
            "guidance": [],
        }

        # Build human-readable descriptions for each filter
        for filter_def in parsed_filters.get("filters", []):
            fieldname = filter_def.get("fieldname", "")
            label = filter_def.get("label", fieldname)
            fieldtype = filter_def.get("fieldtype", "")
            options = filter_def.get("options")
            default = filter_def.get("default")
            is_required = filter_def.get("required", False)
            mandatory_depends_on = filter_def.get("mandatory_depends_on")

            # Build description
            description = f"{fieldname}"
            if label and label != fieldname:
                description = f"{fieldname} ({label})"

            # Add type and options info. A constrained value set is listed in
            # full — truncating it hides values the caller is required to choose
            # from, which is the whole point of advertising them (issue #229).
            if fieldtype in VALUE_CONSTRAINED_FIELDTYPES and options and isinstance(options, list):
                description += f" - {fieldtype}, one of: {', '.join(options)}"
            elif fieldtype == "Link" and options:
                description += f" - Link to {options}"
            elif fieldtype:
                description += f" - {fieldtype}"

            # Add default value info
            if default:
                description += f" (default: {default})"

            # Categorize
            if is_required:
                requirements["common_required_filters"].append(description)
            elif mandatory_depends_on:
                requirements["conditional_required_filters"].append(
                    f"{description} when {mandatory_depends_on}"
                )
            else:
                requirements["common_optional_filters"].append(description)

        # Add guidance
        if requirements["common_required_filters"]:
            requirements["guidance"].append(
                f"This report requires {len(requirements['common_required_filters'])} mandatory filters. "
                "All required filters must be provided for successful execution."
            )

        if requirements["common_optional_filters"]:
            requirements["guidance"].append(
                f"Additionally, {len(requirements['common_optional_filters'])} optional filters are available "
                "to refine results; defaults are shown where available."
            )

        if requirements["conditional_required_filters"]:
            requirements["guidance"].append(
                "Conditional filters must be supplied whenever their stated condition is selected."
            )

        return requirements

    def _analyze_filter_requirements(self, report_name: str, report_type: str) -> Dict[str, Any]:
        """Analyze filter requirements for the report (fallback for pattern-based matching)"""
        requirements = {
            "common_required_filters": [],
            "conditional_required_filters": [],
            "common_optional_filters": [],
            "guidance": [],
        }

        # Add specific guidance based on report name patterns
        report_lower = report_name.lower()

        if "sales_analytics" in report_lower or "sales analytics" in report_lower:
            requirements["common_required_filters"] = [
                "doc_type (Sales Invoice, Sales Order, Quotation, etc.)",
                "tree_type (Customer, Item, Territory, etc.)",
                "value_quantity (Value or Quantity)",
            ]
            requirements["common_optional_filters"] = [
                "from_date and to_date (defaults to current fiscal year)",
                "company (uses default company if not specified)",
            ]
            requirements["guidance"].append(
                "For Sales Analytics: Use doc_type='Sales Invoice', tree_type='Customer', and value_quantity='Value' for customer-wise revenue analysis"
            )

        elif "quotation trends" in report_lower:
            requirements["common_required_filters"] = ["based_on (Item, Customer, Territory, etc.)"]
            requirements["common_optional_filters"] = [
                "from_date and to_date (defaults to current fiscal year)",
                "company (uses default company if not specified)",
            ]
            requirements["guidance"].append(
                "For Quotation Trends: based_on field is mandatory - use 'Item' for item-wise trends or 'Customer' for customer-wise analysis"
            )

        elif "profit" in report_lower and "loss" in report_lower:
            requirements["common_required_filters"] = [
                "company",
                "filter_based_on (Fiscal Year or Date Range)",
                "periodicity (Monthly, Quarterly, Half-Yearly, or Yearly)",
            ]
            requirements["conditional_required_filters"] = [
                "period_start_date and period_end_date when filter_based_on='Date Range'",
                "from_fiscal_year and to_fiscal_year when filter_based_on='Fiscal Year'",
            ]
            requirements["guidance"].append(
                "For a date range, use period_start_date and period_end_date; this report does not use "
                "from_date and to_date."
            )

        elif "receivable" in report_lower:
            requirements["common_required_filters"] = ["company"]
            requirements["common_optional_filters"] = ["customer", "as_on_date"]
            requirements["guidance"].append(
                "Accounts Receivable typically needs company filter, optionally filter by specific customer"
            )

        elif "balance_sheet" in report_lower or "balance sheet" in report_lower:
            requirements["common_required_filters"] = [
                "company",
                "filter_based_on (Fiscal Year or Date Range)",
                "periodicity (Monthly, Quarterly, Half-Yearly, or Yearly)",
            ]
            requirements["conditional_required_filters"] = [
                "period_start_date and period_end_date when filter_based_on='Date Range'",
                "from_fiscal_year and to_fiscal_year when filter_based_on='Fiscal Year'",
            ]
            requirements["guidance"].append(
                "For a date range, use period_start_date and period_end_date; this report does not use "
                "as_on_date."
            )

        elif "cash_flow" in report_lower or "cash flow" in report_lower:
            requirements["common_required_filters"] = [
                "company",
                "filter_based_on (Fiscal Year or Date Range)",
                "periodicity (Monthly, Quarterly, Half-Yearly, or Yearly)",
            ]
            requirements["conditional_required_filters"] = [
                "period_start_date and period_end_date when filter_based_on='Date Range'",
                "from_fiscal_year and to_fiscal_year when filter_based_on='Fiscal Year'",
            ]
            requirements["guidance"].append(
                "For a date range, use period_start_date and period_end_date; this report does not use "
                "from_date and to_date."
            )

        # General guidance based on report type
        if report_type == "Script Report":
            requirements["guidance"].append(
                "Script Reports often have mandatory filters - check filter definitions or use filters_definition field for exact requirements"
            )
        elif report_type == "Query Report":
            requirements["guidance"].append(
                "Query Reports may require company or date filters depending on the underlying query"
            )

        return requirements

    def _discover_report_filters(self, report_name: str, report_doc):
        """
        Discover a report's filter contract, recording a diagnostic for every
        source attempted so an empty result is never silent (issues #203, #223).

        Runs for every report type, not just Script Reports.

        Order (first source that yields an answer wins):
            1. ``Report.filters`` child table (structured, no parsing).
            2. JS — on-disk .js file, then the ``Report.javascript`` DB field.
            3. ``Report.query`` ``%(name)s`` placeholders, for Query Reports.

        A Custom Report carries no configuration of its own; its contract is
        that of the report named in ``reference_report``, so discovery follows
        that link before looking anything up.

        Returns:
            (parsed_filters_or_None, discovery_diagnostics dict)
        """
        diagnostics = {"status": "unresolved"}

        source_doc = report_doc
        reference = getattr(report_doc, "reference_report", None)
        if getattr(report_doc, "report_type", None) == "Custom Report" and reference:
            diagnostics["reference_report"] = reference
            try:
                source_doc = frappe.get_doc("Report", reference)
            except Exception as e:
                diagnostics["reference_report_error"] = f"{type(e).__name__}: {e}"

        # --- Source 1: Report.filters child table ---
        child_rows = report_doc.get("filters") or source_doc.get("filters") or []
        diagnostics["filters_child_table"] = {
            "row_count": len(child_rows),
            "status": "success" if child_rows else "empty",
        }
        if child_rows:
            parsed = self._parse_filters_child_table(child_rows)
            if parsed.get("filters"):
                diagnostics["filters_child_table"]["filters_found"] = len(parsed["filters"])
                diagnostics["status"] = "resolved"
                return parsed, diagnostics

        # --- Source 2: JavaScript (disk file, then DB field) ---
        self._last_discovery_diagnostics = {}
        parsed = self._parse_script_report_filters(source_doc.name, source_doc.module)
        diagnostics["javascript"] = getattr(self, "_last_discovery_diagnostics", {})
        if parsed and parsed.get("filters"):
            diagnostics["status"] = "resolved"
            return parsed, diagnostics

        # --- Source 3: Query Report SQL placeholders ---
        sql_parsed, sql_diagnostics = self._filters_from_query_placeholders(source_doc)
        if sql_diagnostics:
            diagnostics["query_placeholders"] = sql_diagnostics
        if sql_parsed is not None:
            diagnostics["status"] = sql_diagnostics["status"]
            return (sql_parsed if sql_parsed.get("filters") else None), diagnostics

        return parsed, diagnostics

    def _filters_from_query_placeholders(self, report_doc):
        """
        Derive a Query Report's filter contract from its SQL placeholders.

        ``frappe.db.sql(query, filters)`` raises when a named placeholder has no
        value, so every ``%(name)s`` in ``Report.query`` is mandatory by
        construction — a stronger statement than anything declared in JS.

        The negative case is just as useful: a non-empty query with no
        placeholders positively establishes that the report takes no filters.
        That is an answer, not a discovery failure.

        Returns:
            (parsed_filters_or_None, diagnostics_or_None)
        """
        if getattr(report_doc, "report_type", None) != "Query Report":
            return None, None

        query = (getattr(report_doc, "query", None) or "").strip()
        if not query:
            return None, {"status": "empty", "note": "report has no stored query"}

        # ``%%`` is an escaped literal percent (LIKE '%%foo%%',
        # date_format(t, '%%H:%%i:%%s')) and must be removed before scanning,
        # or it masks a real positional marker.
        if re.search(r"%s(?!\w)", query.replace("%%", "")):
            return None, {
                "status": "unresolved",
                "note": "query uses positional %s placeholders; filter names cannot be determined",
            }

        names = list(dict.fromkeys(re.findall(r"%\((\w+)\)s", query)))

        if not names:
            return {
                "filters": [],
                "required_filters": [],
                "conditional_required_filters": [],
                "optional_filters": [],
            }, {
                "status": "no_filters_declared",
                "note": "query defines no %(name)s placeholders, so the report takes no filters",
            }

        filters = [
            {"fieldname": name, "label": name.replace("_", " ").title(), "required": True} for name in names
        ]
        return {
            "filters": filters,
            "required_filters": names,
            "conditional_required_filters": [],
            "optional_filters": [],
        }, {
            "status": "resolved",
            "placeholders": names,
            "note": (
                "filters derived from %(name)s placeholders in the report SQL; every placeholder is "
                "mandatory because the query fails without it. Field types are not declared in SQL."
            ),
        }

    def _parse_filters_child_table(self, child_rows) -> Dict[str, Any]:
        """Convert ``Report.filters`` child-table rows to the parsed-filter shape."""
        filters = []
        for row in child_rows:
            fieldname = row.get("fieldname")
            if not fieldname:
                continue
            is_required = bool(row.get("mandatory") or row.get("reqd"))
            filter_def = {
                "fieldname": fieldname,
                "label": row.get("label") or fieldname,
                "fieldtype": row.get("fieldtype"),
                "options": row.get("options"),
                "default": row.get("default_value") or row.get("default"),
                "required": is_required,
                "depends_on": row.get("depends_on"),
                "mandatory_depends_on": row.get("mandatory_depends_on"),
            }
            # Drop empty keys for a clean payload.
            filter_def = {k: v for k, v in filter_def.items() if v not in (None, "")}
            filter_def["required"] = is_required
            filters.append(filter_def)

        return self._build_parsed_filter_result(filters)

    @staticmethod
    def _build_parsed_filter_result(filters: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Build the canonical parsed-filter payload and preserve conditional requirements.

        Every discovery source funnels through here, so it is also where a
        constrained value set is normalised to an explicit list.
        """
        required_filters = []
        conditional_required_filters = []
        optional_filters = []

        for filter_def in filters:
            fieldname = filter_def.get("fieldname")
            if not fieldname:
                continue
            normalize_filter_options(filter_def)
            if filter_def.get("required"):
                required_filters.append(fieldname)
            elif filter_def.get("mandatory_depends_on"):
                conditional_required_filters.append(fieldname)
            else:
                optional_filters.append(fieldname)

        return {
            "filters": filters,
            "required_filters": required_filters,
            "conditional_required_filters": conditional_required_filters,
            "optional_filters": optional_filters,
        }

    @staticmethod
    def _find_matching_delimiter(text: str, start: int, opening: str, closing: str) -> int:
        """Return the matching delimiter while ignoring strings and JavaScript comments."""
        if start < 0 or start >= len(text) or text[start] != opening:
            return -1

        depth = 0
        quote = None
        escaped = False
        in_line_comment = False
        in_block_comment = False
        index = start

        while index < len(text):
            char = text[index]
            next_char = text[index + 1] if index + 1 < len(text) else ""

            if in_line_comment:
                if char in "\r\n":
                    in_line_comment = False
                index += 1
                continue

            if in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                    index += 2
                else:
                    index += 1
                continue

            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue

            if char == "/" and next_char == "/":
                in_line_comment = True
                index += 2
                continue
            if char == "/" and next_char == "*":
                in_block_comment = True
                index += 2
                continue
            if char in ("'", '"', "`"):
                quote = char
                index += 1
                continue

            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth == 0:
                    return index

            index += 1

        return -1

    def _resolve_report_js_path(self, report_name: str, module_name: str):
        """
        Resolve the on-disk path of a Script Report's .js file.

        Uses Frappe's own resolution (``get_module_path`` + ``scrub``) rather
        than reconstructing the path by looping over installed apps, so custom
        apps with non-trivial package layouts resolve correctly. Returns None
        for custom (DB-only) modules, which have no disk path (issue #203).

        Returns:
            Absolute path string, or None if the module has no disk location.
        """
        import os

        from frappe.modules import get_module_path, scrub

        # Custom modules exist only in the DB (no files on disk).
        if frappe.get_cached_value("Module Def", module_name, "custom"):
            return None

        module_path = get_module_path(module_name)
        report_folder = scrub(report_name)
        return os.path.join(module_path, "report", report_folder, f"{report_folder}.js")

    def _extract_filters_from_js(self, js_content: str):
        """
        Extract filters from either a literal array or a local builder function.

        Returns:
            (parsed_filters_or_None, diagnostic_note). diagnostic_note explains
            why nothing was parsed, so callers can surface it.
        """
        import re

        property_matches = list(re.finditer(r'(?<![\w$])["\']?filters["\']?\s*:', js_content))
        if not property_matches:
            return None, "no 'filters:' key found in JS"

        notes = []
        for property_match in property_matches:
            value_start = property_match.end()
            while value_start < len(js_content) and js_content[value_start].isspace():
                value_start += 1

            if value_start < len(js_content) and js_content[value_start] == "[":
                bracket_end = self._find_matching_delimiter(js_content, value_start, "[", "]")
                if bracket_end == -1:
                    notes.append("mismatched brackets in filters array")
                    continue
                parsed = self._parse_js_filter_array(js_content[value_start + 1 : bracket_end])
                if parsed.get("filters"):
                    return parsed, None
                notes.append("filters array found but no filter objects parsed")
                continue

            function_match = re.match(r"([A-Za-z_$][\w$]*)\s*\(", js_content[value_start:])
            if function_match:
                function_name = function_match.group(1)
                parsed, note = self._extract_filters_from_builder_function(js_content, function_name)
                if parsed:
                    return parsed, None
                notes.append(note or f"unable to resolve filter builder {function_name}()")
                continue

            notes.append("'filters:' value is neither a literal array nor a local builder function")

        return None, "; ".join(dict.fromkeys(notes))

    def _extract_filters_from_builder_function(self, js_content: str, function_name: str):
        """Resolve ``filters: get_filters()`` when the builder is defined in the same JS file."""
        import re

        escaped_name = re.escape(function_name)
        patterns = [
            rf"function\s+{escaped_name}\s*\([^)]*\)\s*\{{",
            rf"(?:const|let|var)\s+{escaped_name}\s*=\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{{",
        ]
        function_match = next(
            (match for pattern in patterns if (match := re.search(pattern, js_content))),
            None,
        )
        if not function_match:
            return None, f"filter builder {function_name}() is not defined in this JS file"

        body_start = js_content.find("{", function_match.start())
        body_end = self._find_matching_delimiter(js_content, body_start, "{", "}")
        if body_end == -1:
            return None, f"filter builder {function_name}() has mismatched braces"
        body = js_content[body_start + 1 : body_end]

        direct_return = re.search(r"\breturn\s*\[", body)
        if direct_return:
            array_start = body.find("[", direct_return.start())
            array_end = self._find_matching_delimiter(body, array_start, "[", "]")
            if array_end != -1:
                parsed = self._parse_js_filter_array(body[array_start + 1 : array_end])
                if parsed.get("filters"):
                    return parsed, None

        for returned_variable in re.finditer(r"\breturn\s+([A-Za-z_$][\w$]*)\s*;?", body):
            variable_name = re.escape(returned_variable.group(1))
            assignment = re.search(rf"(?:const|let|var)\s+{variable_name}\s*=\s*\[", body)
            if assignment:
                array_start = body.find("[", assignment.start())
                array_end = self._find_matching_delimiter(body, array_start, "[", "]")
                if array_end != -1:
                    parsed = self._parse_js_filter_array(body[array_start + 1 : array_end])
                    if parsed.get("filters"):
                        return parsed, None

        return None, f"filter builder {function_name}() does not return a parseable filter array"

    @staticmethod
    def _extract_shared_filter_reference(js_content: str):
        """Return a namespace mixed into a report config, such as ``erpnext.financial_statements``."""
        import re

        namespace_pattern = r"([A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)+)"
        patterns = [
            r"\$\s*\.\s*extend\s*\(\s*(?:\{\s*\}\s*,\s*)?" + namespace_pattern,
            r"Object\s*\.\s*assign\s*\(\s*(?:\{\s*\}\s*,\s*)?" + namespace_pattern,
        ]
        for pattern in patterns:
            match = re.search(pattern, js_content)
            if match:
                return "".join(match.group(1).split())
        return None

    @staticmethod
    def _resolve_shared_js_path(reference: str, module_name: str):
        """Resolve a conventional shared namespace to its app ``public/js`` source file."""
        import os

        from frappe.modules.utils import get_module_app

        app_name = get_module_app(module_name)
        source_name = reference.rsplit(".", 1)[-1]
        candidate = frappe.get_app_path(app_name, "public", "js", f"{source_name}.js")
        return candidate if os.path.isfile(candidate) else None

    def _extract_pushed_filters_from_js(self, js_content: str) -> Dict[str, Any]:
        """Parse report-specific filters appended with ``filters.push(...)``."""
        import re

        filters = []
        pattern = re.compile(r"(?:\.\s*filters|\[\s*[\"']filters[\"']\s*\])\s*\.\s*push\s*\(")
        for match in pattern.finditer(js_content):
            parenthesis_start = match.end() - 1
            parenthesis_end = self._find_matching_delimiter(js_content, parenthesis_start, "(", ")")
            if parenthesis_end == -1:
                continue
            parsed = self._parse_js_filter_array(js_content[parenthesis_start + 1 : parenthesis_end])
            filters.extend(parsed.get("filters", []))
        return self._build_parsed_filter_result(filters)

    def _merge_parsed_filters(self, base: Dict[str, Any], extension: Dict[str, Any]) -> Dict[str, Any]:
        """Merge parsed filter sets by fieldname while keeping report-specific overrides."""
        merged = []
        positions = {}
        for filter_def in [*base.get("filters", []), *extension.get("filters", [])]:
            fieldname = filter_def.get("fieldname")
            if not fieldname:
                continue
            if fieldname in positions:
                merged[positions[fieldname]] = filter_def
            else:
                positions[fieldname] = len(merged)
                merged.append(filter_def)
        return self._build_parsed_filter_result(merged)

    def _parse_report_js(self, js_content: str, module_name: str):
        """Parse direct, locally built, or shared report filters plus appended filters."""
        details = {}
        appended = self._extract_pushed_filters_from_js(js_content)
        details["appended_filters_found"] = len(appended.get("filters", []))

        parsed, note = self._extract_filters_from_js(js_content)
        details["direct"] = {
            "status": "success" if parsed else "failed",
            "filters_found": len(parsed.get("filters", [])) if parsed else 0,
        }
        if note:
            details["direct"]["note"] = note
        if parsed:
            details["source"] = "report_js"
            return self._merge_parsed_filters(parsed, appended), details

        shared_reference = self._extract_shared_filter_reference(js_content)
        details["shared"] = {"reference": shared_reference}
        if not shared_reference:
            details["shared"]["status"] = "not_found"
            return None, details

        try:
            shared_path = self._resolve_shared_js_path(shared_reference, module_name)
        except Exception as e:
            details["shared"].update({"status": "failed", "error": f"{type(e).__name__}: {str(e)}"})
            return None, details

        details["shared"]["path"] = shared_path
        details["shared"]["file_exists"] = bool(shared_path)
        if not shared_path:
            details["shared"]["status"] = "not_found"
            return None, details

        # nosemgrep: frappe-security-file-traversal — path is resolved from trusted Module Def and a validated JS namespace
        with open(shared_path, encoding="utf-8") as shared_file:
            shared_content = shared_file.read()
        shared_parsed, shared_note = self._extract_filters_from_js(shared_content)
        details["shared"]["status"] = "success" if shared_parsed else "failed"
        details["shared"]["filters_found"] = len(shared_parsed.get("filters", [])) if shared_parsed else 0
        if shared_note:
            details["shared"]["note"] = shared_note
        if not shared_parsed:
            return None, details

        details["source"] = "shared_js"
        return self._merge_parsed_filters(shared_parsed, appended), details

    def _parse_script_report_filters(self, report_name: str, module_name: str) -> Dict[str, Any]:
        """
        Parse JavaScript filter definitions for a Script Report.

        Tries the on-disk .js file first (path resolved via Frappe), then falls
        back to the ``Report.javascript`` DB field (covers custom DB-only
        modules and reports whose JS lives in the doc). Stores a diagnostic of
        what was attempted on ``frappe.local`` for the caller to surface.

        Returns:
            Dictionary containing parsed filters, or None if parsing fails.
        """
        import os

        diag = {"js_file": {}, "js_db_field": {}}
        try:
            # --- Source 1: on-disk .js file ---
            js_path = self._resolve_report_js_path(report_name, module_name)
            diag["js_file"]["path"] = js_path
            if js_path and os.path.exists(js_path):
                diag["js_file"]["file_exists"] = True
                diag["js_file"]["file_readable"] = os.access(js_path, os.R_OK)
                # nosemgrep: frappe-security-file-traversal — path built from frappe.get_module_path + scrubbed report metadata, not user input
                with open(js_path, encoding="utf-8") as f:
                    js_content = f.read()
                parsed, parsing_details = self._parse_report_js(js_content, module_name)
                diag["js_file"]["status"] = "success" if parsed else "failed"
                diag["js_file"]["filters_found"] = len(parsed["filters"]) if parsed else 0
                diag["js_file"]["parsing"] = parsing_details
                if parsed:
                    self._last_discovery_diagnostics = diag
                    return parsed
            else:
                diag["js_file"]["file_exists"] = False

            # --- Source 2: Report.javascript DB field ---
            js_db = frappe.db.get_value("Report", report_name, "javascript")
            diag["js_db_field"]["present"] = bool(js_db)
            if js_db:
                parsed, parsing_details = self._parse_report_js(js_db, module_name)
                diag["js_db_field"]["status"] = "success" if parsed else "failed"
                diag["js_db_field"]["filters_found"] = len(parsed["filters"]) if parsed else 0
                diag["js_db_field"]["parsing"] = parsing_details
                if parsed:
                    self._last_discovery_diagnostics = diag
                    return parsed

            self._last_discovery_diagnostics = diag
            return None

        except Exception as e:
            diag["error"] = f"{type(e).__name__}: {str(e)}"
            self._last_discovery_diagnostics = diag
            frappe.log_error(f"Error parsing Script Report filters for {report_name}: {str(e)}")
            return None

    def _parse_js_filter_array(self, filters_text: str) -> Dict[str, Any]:
        """
        Parse JavaScript filter array text into Python dictionary.

        Args:
            filters_text: String containing JavaScript filter objects

        Returns:
            Dictionary with 'filters', 'required_filters', 'optional_filters'
        """
        import re

        filters = []

        # Split into top-level filter objects while ignoring braces in strings/comments.
        filter_objects = []
        index = 0
        while index < len(filters_text):
            object_start = filters_text.find("{", index)
            if object_start == -1:
                break
            object_end = self._find_matching_delimiter(filters_text, object_start, "{", "}")
            if object_end == -1:
                break
            filter_objects.append(filters_text[object_start + 1 : object_end])
            index = object_end + 1

        for filter_obj in filter_objects:
            filter_def = {}

            # Keys may be bare (fieldname:) or quoted (JSON-style "fieldname":),
            # and may use template literals (`x`). Tolerate optional surrounding
            # quotes on the key so JSON-style report JS isn't silently skipped
            # (issue #203).
            # Extract fieldname
            fieldname_match = re.search(r'["\']?fieldname["\']?\s*:\s*[`"\']([^`"\']+)[`"\']', filter_obj)
            if fieldname_match:
                filter_def["fieldname"] = fieldname_match.group(1)
            else:
                continue  # Skip if no fieldname

            # Extract label — supports __("x"), "x", and `x` (template literal),
            # with bare or quoted key.
            label_match = re.search(
                r'["\']?label["\']?\s*:\s*__\(\s*[`"\']([^`"\']+)[`"\']\s*\)'
                r'|["\']?label["\']?\s*:\s*[`"\']([^`"\']+)[`"\']',
                filter_obj,
            )
            if label_match:
                filter_def["label"] = label_match.group(1) or label_match.group(2)

            # Extract fieldtype
            fieldtype_match = re.search(r'["\']?fieldtype["\']?\s*:\s*["\']([^"\']+)["\']', filter_obj)
            if fieldtype_match:
                filter_def["fieldtype"] = fieldtype_match.group(1)

            # Extract options (can be array or string)
            options_match = re.search(
                r'["\']?options["\']?\s*:\s*(\[[\s\S]*?\]|["\'][^"\']+["\'])', filter_obj
            )
            if options_match:
                options_str = options_match.group(1)
                if options_str.startswith("["):
                    # Object options have explicit values and translated labels;
                    # return only values so callers do not receive duplicates.
                    option_values = re.findall(
                        r'["\']?value["\']?\s*:\s*[`"\']([^`"\']+)[`"\']',
                        options_str,
                    )
                    if not option_values:
                        option_values = _extract_js_string_literals(options_str)
                    filter_def["options"] = option_values
                else:
                    # String format (e.g., Link to DocType)
                    filter_def["options"] = options_str.strip("\"'")

            # Extract default value
            default_match = re.search(
                r'["\']?default["\']?\s*:\s*["\']([^"\']+)["\']|["\']?default["\']?\s*:\s*(\d+)',
                filter_obj,
            )
            if default_match:
                filter_def["default"] = default_match.group(1) or default_match.group(2)

            # Extract required flag
            reqd_match = re.search(r'["\']?reqd["\']?\s*:\s*(1|true)', filter_obj, re.IGNORECASE)
            filter_def["required"] = bool(reqd_match)

            for condition_name in ("depends_on", "mandatory_depends_on"):
                condition_match = re.search(
                    rf'(?<![\w$])["\']?{condition_name}["\']?\s*:\s*([`"\'])(.*?)\1',
                    filter_obj,
                    re.DOTALL,
                )
                if condition_match:
                    filter_def[condition_name] = condition_match.group(2)

            filters.append(filter_def)

        return self._build_parsed_filter_result(filters)

    def _get_comprehensive_metadata(self, report_name: str) -> Dict[str, Any]:
        """Get comprehensive report metadata - merged from get_report_data functionality"""
        try:
            # Check if report exists
            if not frappe.db.exists("Report", report_name):
                return {"error": f"Report '{report_name}' not found"}

            # Get report document
            report = frappe.get_doc("Report", report_name)

            # Check permission
            if not frappe.has_permission("Report", "read", report):
                return {"error": f"Insufficient permissions to access report '{report_name}'"}

            # Build comprehensive metadata
            metadata = {
                "basic_info": {
                    "name": getattr(report, "name", ""),
                    "report_name": getattr(report, "report_name", ""),
                    "report_type": getattr(report, "report_type", ""),
                    "module": getattr(report, "module", ""),
                    "is_standard": getattr(report, "is_standard", False),
                    "disabled": getattr(report, "disabled", False),
                    "description": getattr(report, "description", ""),
                    "ref_doctype": getattr(report, "ref_doctype", ""),
                },
                "system_info": {
                    "creation": str(getattr(report, "creation", "")),
                    "modified": str(getattr(report, "modified", "")),
                    "owner": getattr(report, "owner", ""),
                    "modified_by": getattr(report, "modified_by", ""),
                },
            }

            # Add type-specific technical information
            report_type = getattr(report, "report_type", "")
            if report_type == "Query Report":
                metadata["technical_config"] = {
                    "query": getattr(report, "query", ""),
                    "prepared_report": getattr(report, "prepared_report", False),
                    "disable_prepared_report": getattr(report, "disable_prepared_report", False),
                }
            elif report_type == "Script Report":
                metadata["technical_config"] = {
                    "has_javascript": bool(getattr(report, "javascript", "")),
                    "has_json_config": bool(getattr(report, "json", "")),
                }

            # Try to extract advanced filter configuration
            try:
                if report_type == "Query Report" and getattr(report, "json", ""):
                    import json

                    report_config = json.loads(report.json)
                    if "filters" in report_config:
                        metadata["advanced_filters"] = report_config["filters"]

                elif report_type == "Script Report":
                    # NEW: Parse JavaScript file for filter definitions
                    module_name = report.module
                    parsed_filters = self._parse_script_report_filters(report_name, module_name)

                    if parsed_filters:
                        metadata["advanced_filters"] = parsed_filters
                    else:
                        # Fallback: Try Python module (legacy support)
                        report_module_name = f"{module_name}.report.{report.name.lower().replace(' ', '_')}"
                        try:
                            report_module = frappe.get_module(report_module_name)
                            if hasattr(report_module, "get_filters"):
                                metadata["advanced_filters"] = report_module.get_filters()
                            elif hasattr(report_module, "filters"):
                                metadata["advanced_filters"] = report_module.filters
                        except Exception:
                            pass
            except Exception as e:
                frappe.logger().debug(f"Error extracting filters for {report_name}: {str(e)}")

            return metadata

        except Exception as e:
            return {"error": f"Error getting metadata: {str(e)}"}


# Make sure class name matches file name for discovery
report_requirements = ReportRequirements
