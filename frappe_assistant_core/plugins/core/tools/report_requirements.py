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

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe import _

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.core.tools.js_filter_resolver import resolve_filters

# A JS namespace such as ``erpnext.financial_statements``. Anything that does
# not look like this is never turned into a filesystem lookup.
_NAMESPACE_RE = re.compile(r"\A[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+\Z")

# Guards for the bounded search that locates a shared namespace's source file.
_JS_SEARCH_MAX_BYTES = 512 * 1024
_JS_SEARCH_SKIP_DIRS = {"node_modules", "dist", "build", ".git", "__pycache__"}

# Sentinel cached for a namespace that no installed app defines, so the search
# is not repeated on every call.
_NAMESPACE_MISS = "\x00miss"


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
        self.description = "Get report metadata including required and optional filters, columns, and execution requirements for Script Reports, Query Reports, and Custom Reports. Use this tool before executing reports to understand what filters are mandatory, what exact filter values are valid, and how to structure the report request. This prevents filter errors and helps plan successful report execution. Returns complete report metadata including filter definitions with field types (Link, Select, Date), valid enum options for select fields, column structure, report type, and capabilities. IMPORTANT: Use this FIRST before calling generate_report to understand what exact filter values are needed - Link fields require exact database names (e.g., exact Company name, Customer name), Select fields show valid enum values. Essential when generate_report returns filter errors or when planning complex report execution. Filter definitions are read from the report's stored configuration and JavaScript; where a value is computed in the browser at runtime the response says so via 'default_source'/'options_source' rather than guessing. Check 'filter_discovery_status': 'no_filters_declared' means the report genuinely takes no filters, while 'unresolved' means discovery failed and 'discovery_diagnostics' explains why. NOTE: Report Builder reports store a saved filter configuration rather than a filter contract and are not yet fully supported."
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

                # Filter discovery runs for every report type. Gating it to
                # Script Reports left Query and Custom Reports with no filter
                # definitions AND no diagnostics — indistinguishable from a
                # report that genuinely takes none (issue #220).
                parsed, diagnostics = self._discover_report_filters(report_name, report_doc)
                result["discovery_diagnostics"] = diagnostics
                result["filter_discovery_status"] = diagnostics.get("status", "unresolved")

                if parsed is not None:
                    result["filters_definition"] = parsed["filters"]
                    result["required_filter_names"] = parsed["required_filters"]
                    result["optional_filter_names"] = parsed["optional_filters"]
                    if parsed["conditional_filters"]:
                        result["conditional_filter_names"] = parsed["conditional_filters"]
                    result["filter_requirements"] = self._build_requirements_from_parsed_filters(parsed)
                else:
                    result["filter_requirements"] = self._generic_filter_guidance(
                        column_result.get("report_type"), diagnostics
                    )

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

    # ------------------------------------------------------------------
    # Filter discovery
    # ------------------------------------------------------------------

    def _discover_report_filters(self, report_name: str, report_doc) -> Tuple[Optional[Dict], Dict]:
        """
        Discover a report's filter contract, recording a diagnostic for every
        source attempted so an empty result is never silent (issues #203, #220).

        Order (first source that yields an answer wins):
            1. ``Report.filters`` child table — structured, no parsing.
            2. JavaScript — on-disk ``.js``, then the ``Report.javascript`` field.

        A Custom Report carries no configuration of its own; its contract is
        that of the report it references, so discovery follows that link.

        Returns:
            ``(parsed_filters_or_None, diagnostics)``. ``parsed_filters`` is
            not None even for a report with zero filters, as long as discovery
            positively established that — see ``diagnostics["status"]``.
        """
        diagnostics: Dict[str, Any] = {"status": "unresolved"}

        js_doc = report_doc
        reference = getattr(report_doc, "reference_report", None)
        if getattr(report_doc, "report_type", None) == "Custom Report" and reference:
            diagnostics["reference_report"] = reference
            try:
                js_doc = frappe.get_doc("Report", reference)
            except Exception as e:
                diagnostics["reference_report_error"] = f"{type(e).__name__}: {e}"

        # --- Source 1: Report.filters child table ---
        child_rows = report_doc.get("filters") or js_doc.get("filters") or []
        diagnostics["filters_child_table"] = {
            "row_count": len(child_rows),
            "status": "success" if child_rows else "empty",
        }
        if child_rows:
            parsed = self._parse_filters_child_table(child_rows)
            if parsed["filters"]:
                diagnostics["filters_child_table"]["filters_found"] = len(parsed["filters"])
                diagnostics["status"] = "resolved"
                diagnostics["requiredness"] = "declared_in_report_filters"
                return parsed, diagnostics

        # --- Source 2: JavaScript (disk file, then DB field) ---
        js_diag = {"js_file": {}, "js_db_field": {}}
        diagnostics["javascript"] = js_diag
        resolution = None

        try:
            js_path = self._resolve_report_js_path(js_doc.name, js_doc.module)
            js_diag["js_file"]["path"] = js_path
            if js_path and os.path.exists(js_path):
                js_diag["js_file"]["file_exists"] = True
                js_diag["js_file"]["file_readable"] = os.access(js_path, os.R_OK)
                # nosemgrep: frappe-security-file-traversal — path built from frappe.get_module_path + scrubbed report metadata, not user input
                with open(js_path, encoding="utf-8") as f:
                    js_content = f.read()
                resolution = resolve_filters(
                    js_content, report_name=js_doc.name, load_shared=self._load_shared_namespace
                )
                self._record_resolution(js_diag["js_file"], resolution)
            else:
                js_diag["js_file"]["file_exists"] = False

            if resolution is None or resolution.status == "unresolved":
                js_db = frappe.db.get_value("Report", js_doc.name, "javascript")
                js_diag["js_db_field"]["present"] = bool(js_db)
                if js_db:
                    db_resolution = resolve_filters(
                        js_db, report_name=js_doc.name, load_shared=self._load_shared_namespace
                    )
                    self._record_resolution(js_diag["js_db_field"], db_resolution)
                    if db_resolution.status != "unresolved":
                        resolution = db_resolution

        except Exception as e:
            js_diag["error"] = f"{type(e).__name__}: {str(e)}"
            frappe.log_error(f"Error parsing report filters for {report_name}: {str(e)}")

        # --- Source 3: Query Report SQL placeholders ---
        # A Query Report's ``%(fieldname)s`` placeholders are a *binding*
        # contract: frappe.db.sql() raises if one is missing. Equally, a
        # non-empty query with no placeholders positively establishes that the
        # report takes no filters — an answer, not a failure.
        if resolution is None or resolution.status == "unresolved":
            sql_parsed, sql_diag = self._filters_from_query_placeholders(js_doc)
            if sql_diag:
                diagnostics["query_placeholders"] = sql_diag
            if sql_parsed is not None:
                diagnostics["status"] = sql_diag["status"]
                diagnostics["requiredness"] = "declared_in_sql_placeholders"
                return sql_parsed, diagnostics

        if resolution is None or resolution.status == "unresolved":
            return None, diagnostics

        diagnostics["status"] = resolution.status
        diagnostics["requiredness"] = "declared_in_js"
        if resolution.partial:
            diagnostics["partial"] = True

        return self._categorize_filters(resolution.filters), diagnostics

    def _filters_from_query_placeholders(self, report_doc) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Derive a Query Report's filter contract from its SQL placeholders."""
        if getattr(report_doc, "report_type", None) != "Query Report":
            return None, None

        query = (getattr(report_doc, "query", None) or "").strip()
        if not query:
            return None, {"status": "empty", "note": "report has no stored query"}

        # Positional %s placeholders carry no names, so no contract can be read.
        # `%%` is an escaped literal percent (e.g. LIKE '%%foo%%') and must be
        # removed before the scan, otherwise it masks a real positional marker.
        # The scan must NOT exclude `%s)` — `IN (%s)` is the commonest shape,
        # and treating it as "no placeholders" would positively assert that a
        # parameterised report takes no filters.
        if re.search(r"%s(?!\w)", query.replace("%%", "")):
            return None, {
                "status": "unresolved",
                "note": "query uses positional %s placeholders; filter names cannot be determined",
            }

        names = []
        for name in re.findall(r"%\((\w+)\)s", query):
            if name not in names:
                names.append(name)

        if not names:
            return self._categorize_filters([]), {
                "status": "no_filters_declared",
                "note": "query defines no %(name)s placeholders, so the report takes no filters",
            }

        filters = [
            {
                "fieldname": name,
                "label": name.replace("_", " ").title(),
                "required": True,
            }
            for name in names
        ]
        return self._categorize_filters(filters), {
            "status": "resolved",
            "placeholders": names,
            "note": "filters derived from %(name)s placeholders in the report SQL; every placeholder is "
            "mandatory because the query fails without it. Field types are not declared in SQL.",
        }

    @staticmethod
    def _record_resolution(target: Dict[str, Any], resolution) -> None:
        """Fold a resolver outcome into the diagnostics payload."""
        target["status"] = resolution.status
        target["filters_found"] = len(resolution.filters)
        if resolution.sources:
            target["resolved_from"] = resolution.sources
        if resolution.partial:
            target["partial"] = True
        if resolution.notes:
            target["note"] = "; ".join(resolution.notes)

    @staticmethod
    def _categorize_filters(filters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Split resolved filters into required / conditional / optional names."""
        required, optional, conditional = [], [], []
        for filter_def in filters:
            name = filter_def["fieldname"]
            if filter_def.get("required"):
                required.append(name)
            elif filter_def.get("mandatory_depends_on"):
                conditional.append(name)
            else:
                optional.append(name)
        return {
            "filters": filters,
            "required_filters": required,
            "optional_filters": optional,
            "conditional_filters": conditional,
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
            }
            # Drop empty keys for a clean payload.
            filter_def = {k: v for k, v in filter_def.items() if v not in (None, "")}
            filter_def["required"] = is_required
            filters.append(filter_def)

        return self._categorize_filters(filters)

    def _resolve_report_js_path(self, report_name: str, module_name: str) -> Optional[str]:
        """
        Resolve the on-disk path of a report's .js file.

        Uses Frappe's own resolution (``get_module_path`` + ``scrub``) rather
        than reconstructing the path by looping over installed apps, so custom
        apps with non-trivial package layouts resolve correctly. Returns None
        for custom (DB-only) modules, which have no disk path (issue #203).
        """
        from frappe.modules import get_module_path, scrub

        if not module_name:
            return None

        # Custom modules exist only in the DB (no files on disk).
        if frappe.get_cached_value("Module Def", module_name, "custom"):
            return None

        module_path = get_module_path(module_name)
        report_folder = scrub(report_name)
        return os.path.join(module_path, "report", report_folder, f"{report_folder}.js")

    # ------------------------------------------------------------------
    # Shared-namespace resolution (injected into the frappe-free resolver)
    # ------------------------------------------------------------------

    def _load_shared_namespace(self, namespace: str) -> Optional[str]:
        """
        Return the JavaScript source that defines *namespace*, or None.

        Report JS commonly inherits its filters from a shared object such as
        ``erpnext.financial_statements``. The namespace does NOT reliably map
        to a file path (``erpnext.pre_sales`` lives in ``utils/sales_common.js``,
        ``hrms.leave_utils`` in ``utils/leave_utils.js``), so the definition
        site is located by a bounded content search rather than by building a
        path out of the namespace segments.

        The search is confined to installed apps' ``public/js`` trees, skips
        vendored/build directories and caps file size. Both hits and misses are
        cached: a miss costs a full walk of every installed app's public/js
        (~27ms on a six-app bench, and it grows with the number of apps), and
        without a negative entry that walk would repeat on every call. Run
        ``bench clear-cache`` after installing an app that adds a new shared
        namespace.
        """
        if not namespace or not _NAMESPACE_RE.match(namespace):
            return None

        cached_path = frappe.cache().hget("fac_js_namespace_path", namespace)
        if cached_path == _NAMESPACE_MISS:
            return None
        if cached_path and os.path.exists(cached_path):
            return self._read_js(cached_path)

        needles = (
            f"{namespace} =",
            f"{namespace}=",
            f'frappe.provide("{namespace}")',
            f"frappe.provide('{namespace}')",
        )

        try:
            installed = frappe.get_installed_apps()
        except Exception:
            return None

        # The namespace root is usually the app name; try it first, then the
        # remaining apps, so the common case costs one directory walk.
        root = namespace.split(".", 1)[0]
        apps = ([root] if root in installed else []) + [a for a in installed if a != root]

        for app in apps:
            js_root = self._app_js_root(app)
            if not js_root:
                continue
            for path in self._iter_js_files(js_root):
                content = self._read_js(path)
                if content and any(needle in content for needle in needles):
                    frappe.cache().hset("fac_js_namespace_path", namespace, path)
                    return content

        frappe.cache().hset("fac_js_namespace_path", namespace, _NAMESPACE_MISS)
        return None

    @staticmethod
    def _app_js_root(app: str) -> Optional[str]:
        try:
            js_root = os.path.realpath(frappe.get_app_path(app, "public", "js"))
        except Exception:
            return None
        return js_root if os.path.isdir(js_root) else None

    @staticmethod
    def _iter_js_files(js_root: str):
        """Yield .js files under *js_root*, staying inside it and skipping vendored trees."""
        for dirpath, dirnames, filenames in os.walk(js_root):
            dirnames[:] = [d for d in dirnames if d not in _JS_SEARCH_SKIP_DIRS]
            for filename in filenames:
                if not filename.endswith(".js") or filename.endswith(".min.js"):
                    continue
                path = os.path.join(dirpath, filename)
                real = os.path.realpath(path)
                # Containment check: a symlink must not lead outside the tree.
                if not real.startswith(js_root + os.sep):
                    continue
                try:
                    if os.path.getsize(real) > _JS_SEARCH_MAX_BYTES:
                        continue
                except OSError:
                    continue
                yield real

    @staticmethod
    def _read_js(path: str) -> Optional[str]:
        try:
            # nosemgrep: frappe-security-file-traversal — path is confined to an installed app's public/js tree by _iter_js_files
            with open(path, encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return None

    # ------------------------------------------------------------------
    # Guidance
    # ------------------------------------------------------------------

    def _build_requirements_from_parsed_filters(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build human-readable filter requirements from resolved filter definitions.
        """
        requirements: Dict[str, Any] = {
            "common_required_filters": [],
            "common_optional_filters": [],
            "conditional_filters": [],
            "guidance": [],
        }

        for filter_def in parsed["filters"]:
            description = self._describe_filter(filter_def)
            if filter_def.get("required"):
                requirements["common_required_filters"].append(description)
            elif filter_def.get("mandatory_depends_on"):
                requirements["conditional_filters"].append(
                    f"{description} - required when: {filter_def['mandatory_depends_on']}"
                )
            else:
                requirements["common_optional_filters"].append(description)

        if requirements["common_required_filters"]:
            requirements["guidance"].append(
                f"This report declares {len(requirements['common_required_filters'])} mandatory filters. "
                "All of them must be provided for successful execution."
            )

        if requirements["conditional_filters"]:
            requirements["guidance"].append(
                "Some filters are mandatory only under a condition (see conditional_filters). "
                "Evaluate the condition against the values you intend to send."
            )

        if requirements["common_optional_filters"]:
            requirements["guidance"].append(
                f"{len(requirements['common_optional_filters'])} optional filters are available to refine results."
            )

        if not parsed["filters"]:
            requirements["guidance"].append("This report declares no filters and can be run without any.")

        # Filters marked required here are the ones the report's own
        # configuration declares. Server-side report code may enforce more, so
        # an empty required list is not a guarantee.
        requirements["guidance"].append(
            "Requiredness reflects what the report configuration declares. Server-side report code may "
            "enforce additional mandatory filters; if execution fails with a 'mandatory' error, supply the "
            "field named in that error."
        )

        return requirements

    @staticmethod
    def _describe_filter(filter_def: Dict[str, Any]) -> str:
        """Render one filter definition as a single readable line."""
        fieldname = filter_def.get("fieldname", "")
        label = filter_def.get("label", fieldname)
        fieldtype = filter_def.get("fieldtype", "")
        options = filter_def.get("options")

        description = fieldname
        if label and label != fieldname:
            description = f"{fieldname} ({label})"

        if fieldtype in ("Select", "Autocomplete") and isinstance(options, list) and options:
            shown = ", ".join(str(o) for o in options[:5])
            if len(options) > 5:
                shown += f", ... ({len(options)} options)"
            description += f" - {fieldtype}: {shown}"
        elif fieldtype in ("Link", "MultiSelectList", "Dynamic Link") and options:
            description += f" - {fieldtype} to {options}"
        elif fieldtype:
            description += f" - {fieldtype}"

        if filter_def.get("options_source") == "runtime":
            description += " (options computed at runtime; query the target DocType for valid values)"

        if filter_def.get("default") is not None:
            description += f" (default: {filter_def['default']})"
        elif filter_def.get("default_source") == "runtime":
            expr = filter_def.get("default_expr")
            description += f" (default supplied by the UI at runtime{': ' + expr if expr else ''})"

        if filter_def.get("depends_on") and not filter_def.get("mandatory_depends_on"):
            description += f" (shown when: {filter_def['depends_on']})"

        return description

    @staticmethod
    def _generic_filter_guidance(report_type: str, diagnostics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Guidance for reports whose filter contract could not be resolved.

        This deliberately asserts nothing about which filters exist. The
        previous implementation guessed from the report's name and was wrong
        for every report it matched on this bench — it claimed Profit and Loss
        Statement needs ``from_date``/``to_date`` and Balance Sheet needs
        ``as_on_date``, none of which exist on those reports. A wrong filter
        list is worse than no list: the caller sends fabricated values, gets an
        empty result, and reports it as a finding.
        """
        guidance = []
        guidance.append(
            "Filter definitions could not be determined for this report - see discovery_diagnostics "
            "for what was attempted and why it failed."
        )
        guidance.append(
            "Do not guess filter names. Run the report with no filters to see what the server "
            "requires, or inspect the report definition directly."
        )

        if report_type == "Query Report":
            guidance.append(
                "Query Reports take their filters from the Report's filter configuration or its SQL "
                "placeholders; the report may accept no filters at all."
            )
        elif report_type == "Script Report":
            guidance.append(
                "Script Reports define filters in JavaScript, which may build them dynamically in the browser."
            )
        elif report_type == "Report Builder":
            guidance.append(
                "Report Builder reports store a saved column/filter configuration rather than a filter "
                "contract; use the underlying DocType's fields to filter instead."
            )

        return {
            "common_required_filters": [],
            "common_optional_filters": [],
            "conditional_filters": [],
            "guidance": guidance,
        }

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

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
                    # A Custom Report inherits its contract from this report.
                    "reference_report": getattr(report, "reference_report", ""),
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
                else:
                    parsed, _diagnostics = self._discover_report_filters(report_name, report)
                    if parsed:
                        metadata["advanced_filters"] = parsed
            except Exception as e:
                frappe.logger().debug(f"Error extracting filters for {report_name}: {str(e)}")

            return metadata

        except Exception as e:
            return {"error": f"Error getting metadata: {str(e)}"}


# Make sure class name matches file name for discovery
report_requirements = ReportRequirements
