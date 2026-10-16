"""Refuse to run a setup script against a site that was not built for the release check.

Pure Python (no Frappe) so it is unit-tested without a bench. The setup scripts create an
ERPNext demo company and up to 200,000 ledger rows; one mistyped ``--site`` must not put
that into a development or production site.
"""

import json
import os

MARKER = "release_check_site"


def require_release_check_site(sites_path: str, site: str) -> None:
    """Exit unless ``<sites_path>/<site>/site_config.json`` sets ``release_check_site`` truthy."""
    config_file = os.path.join(sites_path, site, "site_config.json")
    try:
        # CLI tool: the path comes from the operator's own --site argument, never a request
        with open(config_file, encoding="utf-8") as handle:  # nosemgrep: frappe-security-file-traversal
            marked = bool(json.load(handle).get(MARKER))
    except (OSError, ValueError, AttributeError):
        marked = False
    if not marked:
        raise SystemExit(
            f"Refusing to write to {site}: it is not marked as a release-check site. If it is one "
            f"you built for this purpose, run: bench --site {site} set-config {MARKER} 1"
        )
