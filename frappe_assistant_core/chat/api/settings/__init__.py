# Frappe Assistant Core - Settings API package
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
Core access, capabilities, registration, widget, uploads, and mobile-usage APIs.

Submodule layout (kept as a package so each topical surface has its own
file, since the original flat module exceeded 1,200 lines):

- ``access``         — pre-auth gate + widget-show decision (``can_use_faco``)
- ``capabilities``   — AR capability + terms proxy
- ``registration``   — site → AR tenant registration + partner-code validation
- ``widget``         — widget settings, copilot status, user preferences,
                       deprecated screen-extract fallback
- ``uploads``        — message-file upload + FACO-H11 validators
- ``mobile_usage``   — usage stats / history / subscription / model-usage

Every public endpoint is re-exported here so the dotted whitelist path
``frappe_assistant_core.chat.api.settings.<func>``
continues to resolve unchanged. Tests import directly from this module
path; that contract is preserved.

Re-export aggregator: F401 is globally ignored in this app's ruff
config, so no per-line noqa is necessary.
"""

from frappe_assistant_core.chat.api.settings.access import (
    can_use_faco,
)
from frappe_assistant_core.chat.api.settings.capabilities import (
    get_ar_terms,
    get_capabilities,
)
from frappe_assistant_core.chat.api.settings.mobile_usage import (
    get_model_usage,
    get_subscription_info,
    get_usage_history,
    get_usage_stats,
)
from frappe_assistant_core.chat.api.settings.registration import (
    _translate_registration_error,
    accept_updated_terms,
    change_pending_owner_email,
    complete_email_verification,
    get_plan_comparison,
    get_registration_state,
    poll_for_rotated_secret,
    register_with_ar,
    request_site_rebind,
    resend_owner_verification,
    reset_registration,
    run_diagnostics,
    validate_partner_code,
)
from frappe_assistant_core.chat.api.settings.uploads import (
    ALLOWED_UPLOAD_EXTENSIONS,
    ALLOWED_UPLOAD_MIMETYPES,
    upload_message_file,
)
from frappe_assistant_core.chat.api.settings.widget import (
    ALLOWED_PREFERENCE_FIELDS,
    extract_screen_content,
    get_copilot_status,
    get_widget_settings,
    update_user_preference,
)
