# Copyright (C) 2025 Promantia
# Developer Tools Plugin — Shared security helpers

import os

import frappe
from frappe import _

PROTECTED_APPS = {
    "frappe",
    "frappe_assistant_core",
    "erpnext",
    "hrms",
    "payments",
    "india_compliance",
    "lending",
    "education",
}


DEV_MODE_REQUIRED_TOOLS = {"bench_execute", "write_file"}


def assert_developer_mode():
    """
    Raises frappe.PermissionError if developer_mode is not enabled in site_config.json.
    Call this as the first line in execute() for tools that modify the bench
    filesystem or run bench operations (bench_execute, write_file).
    """
    if not frappe.conf.get("developer_mode"):
        frappe.throw(
            _(
                "This tool requires developer_mode=1 in site_config.json. "
                "It is not available on production sites."
            ),
            frappe.PermissionError,
        )


def assert_system_manager():
    """
    Raises frappe.PermissionError if current user
    does not have System Manager role.
    Call this as the first line in every tool's execute().
    """
    user = frappe.session.user

    if user == "Guest":
        frappe.throw(_("Guest users are not allowed to use Developer Tools."), frappe.PermissionError)

    if "System Manager" not in frappe.get_roles(user):
        frappe.throw(
            _(
                "User {0} does not have System Manager role. "
                "System Manager is required for all Developer Tools."
            ).format(user),
            frappe.PermissionError,
        )


def resolve_and_validate_path(relative_path):
    """
    Resolves a relative path against the bench apps/ directory.
    Validates:
      - No null bytes
      - Max 10 directory levels deep
      - No path traversal (../../)
      - No symlink escapes outside apps/
    Returns the resolved absolute path if valid.
    Raises frappe.ValidationError if invalid.
    """
    # Null byte check
    if "\x00" in relative_path:
        frappe.throw(_("Invalid path: null bytes are not allowed."), frappe.ValidationError)

    # Depth check
    parts = [p for p in relative_path.replace("\\", "/").split("/") if p]
    if len(parts) > 15:
        frappe.throw(
            _("Invalid path: too many directory levels ({0}). Max is 15.").format(len(parts)),
            frappe.ValidationError,
        )

    # Build full path
    bench_path = frappe.utils.get_bench_path()
    apps_path = os.path.join(bench_path, "apps")
    full_path = os.path.join(apps_path, relative_path)

    # Resolve symlinks and traversal
    real_path = os.path.realpath(full_path)

    # Boundary check
    if not real_path.startswith(apps_path + os.sep) and real_path != apps_path:
        frappe.throw(
            _(
                "Invalid path: resolves outside the apps/ directory. "
                "Path traversal and symlink escapes are not allowed."
            ),
            frappe.ValidationError,
        )

    return real_path
