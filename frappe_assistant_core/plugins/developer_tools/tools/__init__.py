# Copyright (C) 2025 Promantia
# Developer Tools Plugin — Shared security helpers

import os
import frappe

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


def assert_system_manager():
    """
    Raises frappe.PermissionError if current user
    does not have System Manager role.
    Call this as the first line in every tool's execute().
    """
    user = frappe.session.user

    if user == "Guest":
        frappe.throw(
            "Guest users are not allowed to use Developer Tools.",
            frappe.PermissionError
        )

    if "System Manager" not in frappe.get_roles(user):
        frappe.throw(
            f"User {user} does not have System Manager role. "
            f"System Manager is required for all Developer Tools.",
            frappe.PermissionError
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
        frappe.throw(
            "Invalid path: null bytes are not allowed.",
            frappe.ValidationError
        )

    # Depth check
    parts = [p for p in relative_path.replace("\\", "/").split("/") if p]
    if len(parts) > 10:
        frappe.throw(
            f"Invalid path: too many directory levels ({len(parts)}). Max is 10.",
            frappe.ValidationError
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
            f"Invalid path: resolves outside the apps/ directory. "
            f"Path traversal and symlink escapes are not allowed.",
            frappe.ValidationError
        )

    return real_path
