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

# FAC Chat — REST and streaming API endpoints.

"""
API endpoints for FAC Chat.

This package was refactored from a single ``api.py`` monolith into
feature-based modules for maintainability.  Every public function is
re-exported here so that existing Frappe API paths
(``frappe_assistant_core.chat.api.<function>``)
continue to resolve without any callsite changes.

Modules
-------
- chat       — Streaming chat relay, session management
- auth       — User registration, OAuth, MCP server connections
- billing    — Subscription, payments, credits, quota, usage
- settings   — Access checks, capabilities, registration, widget config
- workflows  — Workflow CRUD, execution, scheduling, templates
- documents  — Knowledge-base / RAG document APIs
- prompts    — Prompt templates, suggested prompts
- models     — AI model listing & preference
- users      — Admin user management
- team_instructions — Shared knowledge (editable RAG document)
- events     — Streaming event history & tool stats
"""

# ── Analytics (Admin) ──────────────────────────────────────────────
from .analytics import (
    get_analytics_data,
    get_conversation_analytics,
    get_message_credits,
)

# ── Auth & Registration ─────────────────────────────────────────────
from .auth import (
    connect_fac_mcp_server,
    disconnect_mcp_server,
    get_user_auth_status,
    get_user_mcp_servers,
    oauth_callback,
    reconnect_mcp_server,
)

# ── Billing & Subscription ──────────────────────────────────────────
from .billing import (
    add_user_seat,
    cancel_scheduled_change,
    cancel_subscription,
    create_hosted_checkout,
    downgrade_to_free,
    download_invoice_pdf,
    get_available_gateways,
    get_billing_dashboard,
    get_billing_details,
    get_billing_history,
    get_billing_page_data,
    get_consumption_breakdown,
    get_credit_balance,
    get_expiring_credits,
    get_invoices,
    get_payment_instrument,
    get_payment_methods,
    get_plan_options,
    get_quota_status,
    get_subscription_status,
    get_usage_history,
    initiate_plan_upgrade,
    preview_plan_pricing,
    preview_seat_charge,
    purchase_credits,
    reactivate_subscription,
    reauthorize_mandate,
    remove_user_seat,
    save_billing_details,
    scheduled_sync_subscription,
    sync_subscription_status,
    update_payment_method,
    verify_checkout_return,
    verify_payment,
    verify_razorpay_credit_payment,
    verify_razorpay_payment,
    verify_seat_payment,
)

# ── Chat & Streaming ────────────────────────────────────────────────
from .chat import (
    archive_all_conversations,
    archive_session,
    cancel_stream,
    clear_all_conversations,
    continue_archived_session,
    create_session,
    delete_session,
    get_archived_sessions,
    get_session_history,
    get_user_sessions,
    resume_interrupt,
    send_message,
)

# ── Discovery banner ────────────────────────────────────────────────
from .discovery import (
    dismiss_banner,
    get_chat_analytics,
    get_chat_status,
    should_show_banner,
    toggle_chat,
)

# ── Documents (Knowledge Base) ──────────────────────────────────────
from .documents import (
    delete_document,
    get_document,
    get_document_content,
    get_storage_info,
    list_chunks,
    list_documents,
    update_document_access,
    upload_document,
)

# ── Events ───────────────────────────────────────────────────────────
from .events import (
    get_message_events,
    get_tool_stats,
)

# ── SPA Initialization ─────────────────────────────────────────────
from .init import initialize_spa

# ── Marketplace ─────────────────────────────────────────────────────
from .marketplace import (
    approve_listing,
    check_all_workflow_updates,
    check_workflow_update,
    delete_listing,
    download_listing_as_json,
    get_creator_stats,
    get_listing,
    import_listing,
    list_listings,
    list_my_listings,
    list_pending_reviews,
    publish_workflow,
    rate_listing,
    reject_listing,
    report_listing,
    update_listing,
)

# ── Memories (User Memory Viewer) ────────────────────────────────────
from .memories import (
    delete_all_memories,
    delete_memory,
    get_memory_stats,
    list_memories,
    update_memory,
)

# ── Mobile Streaming ────────────────────────────────────────────────
from .mobile_stream import (
    get_available_models as mobile_get_available_models,
)
from .mobile_stream import (
    get_messages,
    get_sessions,
    search_sessions,
    stream_chat,
)

# ── Models ───────────────────────────────────────────────────────────
from .models import (
    get_available_models,
    set_preferred_model,
)

# ── Profile ──────────────────────────────────────────────────────────
from .profile import (
    get_profile,
    update_profile,
)

# ── Prompts ──────────────────────────────────────────────────────────
from .prompts import (
    get_prompt_templates,
    get_rendered_prompt,
    get_suggested_prompts,
    update_pinned_templates,
)

# ── Settings & Config ───────────────────────────────────────────────
from .settings import (
    accept_updated_terms,
    can_use_faco,
    change_pending_owner_email,
    complete_email_verification,
    extract_screen_content,
    get_ar_terms,
    get_capabilities,
    get_copilot_status,
    get_plan_comparison,
    get_registration_state,
    get_widget_settings,
    poll_for_rotated_secret,
    register_with_ar,
    request_site_rebind,
    resend_owner_verification,
    reset_registration,
    run_diagnostics,
    update_user_preference,
    upload_message_file,
    validate_partner_code,
)

# ── Shared Knowledge ──────────────────────────────────────────────────
from .team_instructions import (
    get_shared_knowledge,
    share_memory_to_knowledge,
    update_shared_knowledge,
)

# ── Users (Admin) ────────────────────────────────────────────────────
from .users import (
    add_user,
    deregister_user,
    get_available_users,
    get_member_audit_log,
    get_my_credit_status,
    get_user_limit_status,
    invite_user,
    list_invites,
    list_users,
    resend_invite,
    revoke_invite,
    set_user_credit_limit,
    suspend_user,
)
from .voice import transcribe as voice_transcribe  # noqa: F401

# ── Workflows ────────────────────────────────────────────────────────
# Marketplace endpoints (list/get/import/rate/report/approve/reject/creator_stats/
# pending_reviews) were moved to api/marketplace.py in chunk 4 of the marketplace
# extraction. They are re-exported above from .marketplace.
from .workflows import (
    cancel_workflow_run,
    create_workflow,
    delete_workflow,
    execute_workflow,
    get_workflow,
    get_workflow_audit_summary,
    get_workflow_run,
    list_user_tools,
    list_workflow_runs,
    list_workflows,
    resolve_workflow_tools,
    run_workflow_node,
    set_workflow_schedule,
    test_workflow_node,
    update_workflow,
    validate_workflow_graph,
)
