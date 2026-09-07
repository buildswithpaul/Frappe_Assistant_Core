# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# AGPL-3.0 License

"""Which AR server this site talks to.

`fac_cloud_url` is environment identity, not a user preference: `tenant_id` and
`tenant_secret` are issued by whichever server it names, so repointing a
registered site silently invalidates them. It therefore resolves from
site_config — per-site, outside git, already managed by devops — with
production compiled in as the fallback:

    bench --site uat.fac-cloud.com set-config fac_cloud_url https://dev.fac-cloud.com
    bench --site dev.localhost     set-config fac_cloud_url http://localhost:8001

The FAC Chat Settings field of the same name is a read-only mirror of this,
refreshed on migrate so Desk and the SPA can show where the site points.
"""

import frappe

PRODUCTION_FAC_CLOUD_URL = "https://api.fac-cloud.com"

DRIFT_LOG_TITLE = "FAC Cloud URL changed"


def get_fac_cloud_url() -> str:
    """Return the AR base URL for this site, without a trailing slash."""
    configured = (frappe.conf.get("fac_cloud_url") or "").strip()
    return (configured or PRODUCTION_FAC_CLOUD_URL).rstrip("/")


def sync_cloud_url_mirror() -> None:
    """Refresh the FAC Chat Settings mirror; shout if a registered site moved.

    Runs on migrate. A site that takes new code before its site_config is
    updated repoints silently — it keeps answering, but signs with credentials
    the new server never issued, so the symptom is a puzzling auth failure far
    from the cause. Naming both URLs here makes it a one-line fix.
    """
    resolved = get_fac_cloud_url()
    previous = (frappe.db.get_single_value("FAC Chat Settings", "fac_cloud_url") or "").rstrip("/")
    registered = frappe.db.get_single_value("FAC Chat Settings", "registration_status") == "Registered"

    if registered and previous and previous != resolved:
        frappe.log_error(
            title=DRIFT_LOG_TITLE,
            message=(
                f"This site is registered against {previous} but now resolves to {resolved}.\n\n"
                f"Its tenant credentials were issued by {previous} and will not authenticate "
                f"against {resolved}.\n\n"
                f"To keep it where it was:\n"
                f"    bench --site {frappe.local.site} set-config fac_cloud_url {previous}"
            ),
        )

    frappe.db.set_single_value("FAC Chat Settings", "fac_cloud_url", resolved)
