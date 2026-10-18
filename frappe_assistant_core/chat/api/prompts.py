# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Prompt templates and suggestion APIs."""

import json

import frappe
from frappe import _, _lt
from frappe.utils import getdate

from frappe_assistant_core.chat.home_preferences import load_home_preferences
from frappe_assistant_core.chat.home_signals import resolve_lenses
from frappe_assistant_core.chat.page_asks import page_asks_for

from ._helpers import _safe_error
from .auth import _ar_user_id, _do_user_recovery, _ensure_user_registered

# Per-user cache of the merged AR prompt catalog. The TTL covers sources we
# can't hook — platform prompts and other MCP servers — while local Prompt
# Template writes invalidate explicitly via clear_prompt_catalog_cache().
_CATALOG_CACHE_PREFIX = "faco_ar_prompt_catalog:"
_CATALOG_CACHE_TTL = 3600


def clear_prompt_catalog_cache():
    """Drop every user's cached AR prompt catalog.

    Site-wide rather than per-author: publishing or sharing a template
    changes what other users see in their slash menu too.
    """
    frappe.cache.delete_keys(_CATALOG_CACHE_PREFIX)


def _get_template_suggestions(context):
    """
    Fetch MCP templates from AR and sort by context relevance.

    Returns:
            tuple: (suggestions_list, raw_templates_data)
            - suggestions_list: list of prompt dicts with source="pinned" or "contextual"
            - raw_templates_data: dict with templates/categories/pinned for templateStore hydration
    """
    context_type = context.get("type", "General")
    doctype = context.get("doctype")
    empty_templates = {"templates": [], "categories": [], "pinned": []}

    try:
        templates_data = get_prompt_templates()
        templates = templates_data.get("templates", [])
        pinned = templates_data.get("pinned", [])

        if not templates:
            return [], empty_templates

        result = []
        added_names = set()

        # Add pinned templates first
        for template in templates:
            if template.get("name") in pinned:
                result.append(
                    {
                        "name": template.get("name"),
                        "description": template.get("description", template.get("name")),
                        "has_arguments": bool(template.get("arguments")),
                        "arguments": template.get("arguments", []),
                        "source": "pinned",
                        "category": template.get("category"),
                    }
                )
                added_names.add(template.get("name"))

        # Sort remaining: context-relevant first, then others
        relevant = []
        other = []

        for template in templates:
            if template.get("name") in added_names:
                continue

            category = (template.get("category") or "").lower()
            template_name = (template.get("name") or "").lower()

            is_relevant = False
            if doctype:
                doctype_lower = doctype.lower().replace(" ", "_")
                is_relevant = (
                    doctype_lower in category
                    or doctype_lower in template_name
                    or ("form" in category and context_type == "Form")
                    or ("list" in category and context_type == "List")
                )
            else:
                is_relevant = "general" in category or "help" in category

            template_obj = {
                "name": template.get("name"),
                "description": template.get("description", template.get("name")),
                "has_arguments": bool(template.get("arguments")),
                "arguments": template.get("arguments", []),
                "source": "contextual",
                "category": template.get("category"),
            }

            if is_relevant:
                relevant.append(template_obj)
            else:
                other.append(template_obj)

        result.extend(relevant)
        result.extend(other)
        return result, templates_data

    except Exception as e:
        frappe.log_error(title="FACO Templates Fallback", message=f"Error fetching templates: {e!s}")
        return [], empty_templates


# Literals so the extractor sees each month name; indexed by today's month.
_MONTH_NAMES = (
    _lt("January"),
    _lt("February"),
    _lt("March"),
    _lt("April"),
    _lt("May"),
    _lt("June"),
    _lt("July"),
    _lt("August"),
    _lt("September"),
    _lt("October"),
    _lt("November"),
    _lt("December"),
)


def _current_month_name() -> str:
    """Translated name of the current month, e.g. "October"."""
    return str(_MONTH_NAMES[getdate().month - 1])


# What a starter produces, so the day-one cards can label it: a chart ("see"),
# a lookup ("find") or a drafted/changed document ("do").
STARTER_KINDS = ("see", "find", "do")


def _lens_prompt(name: str, description: str, subtext: str, kind: str) -> dict:
    return {"name": name, "description": description, "subtext": subtext, "kind": kind}


def _lens_starters() -> dict[str, list[dict]]:
    """Concrete, translated starter questions per lens (built per call so
    ``_()`` resolves in the request language and the month stays current)."""
    return {
        "accounts": [
            _lens_prompt(
                "accounts_top_debtors",
                _("Who owes us the most, and since when?"),
                _("Largest receivables, oldest first"),
                "find",
            ),
            _lens_prompt(
                "accounts_collections_trend",
                _("Compare collections this month with last month"),
                _("Are payments speeding up or slowing down?"),
                "see",
            ),
            _lens_prompt(
                "accounts_gst_payable",
                _("Summarise GST payable for {0}").format(_current_month_name()),
                _("Tax collected against tax paid"),
                "see",
            ),
            _lens_prompt(
                "accounts_payment_reminder",
                _("Draft a payment reminder to my most overdue customer"),
                _("Ready to review before it goes out"),
                "do",
            ),
            _lens_prompt(
                "accounts_late_payers",
                _("Which customers pay late most often?"),
                _("Who to chase first"),
                "find",
            ),
        ],
        "sales": [
            _lens_prompt(
                "sales_top_customers",
                _("Top 10 customers by revenue this month"),
                _("Ranked from your sales invoices"),
                "see",
            ),
            _lens_prompt(
                "sales_pending_orders",
                _("Which sales orders are still waiting to be delivered?"),
                _("What is due and what is stuck"),
                "find",
            ),
            _lens_prompt(
                "sales_quotation_followup",
                _("Draft a follow-up for my oldest open quotation"),
                _("Ready to review before it goes out"),
                "do",
            ),
            _lens_prompt(
                "sales_stale_leads",
                _("Which leads have gone quiet for two weeks?"),
                _("Before they go cold"),
                "find",
            ),
        ],
        "stock": [
            _lens_prompt(
                "stock_low_items",
                _("Which items are below reorder level?"),
                _("Before they run out"),
                "find",
            ),
            _lens_prompt(
                "stock_open_purchase_orders",
                _("Which purchase orders are overdue for delivery?"),
                _("Supplier, value, promised date"),
                "find",
            ),
            _lens_prompt(
                "stock_supplier_spend",
                _("Top suppliers by spend this quarter"),
                _("Concentration at a glance"),
                "see",
            ),
            _lens_prompt(
                "stock_material_request",
                _("Prepare a material request for items below reorder level"),
                _("Drafted for you to review"),
                "do",
            ),
        ],
        "hr": [
            _lens_prompt(
                "hr_on_leave",
                _("Who is on leave this week?"),
                _("From approved leave applications"),
                "find",
            ),
            _lens_prompt(
                "hr_leave_reply",
                _("Draft a reply approving or declining my pending leave requests"),
                _("Ready to review before it goes out"),
                "do",
            ),
            _lens_prompt(
                "hr_attendance_gaps",
                _("Who has missed attendance marking this week?"),
                _("Gaps worth a nudge"),
                "see",
            ),
            _lens_prompt(
                "hr_upcoming_events",
                _("Whose birthdays and work anniversaries are coming up?"),
                _("A small thing worth remembering"),
                "find",
            ),
        ],
        "support": [
            _lens_prompt(
                "support_open_tickets",
                _("Summarise my open tickets by priority"),
                _("Triage in one view"),
                "see",
            ),
            _lens_prompt(
                "support_common_issues",
                _("What are the most common support issues lately?"),
                _("Patterns across recent tickets"),
                "find",
            ),
            _lens_prompt(
                "support_overdue_tickets",
                _("Which tickets are about to breach their response time?"),
                _("Oldest unanswered first"),
                "find",
            ),
            _lens_prompt(
                "support_unassigned_reply",
                _("Draft a reply to my oldest unassigned ticket"),
                _("Ready to review before it goes out"),
                "do",
            ),
        ],
        "generic": [
            _lens_prompt(
                "generic_help",
                _("What can you help me with?"),
                _("A quick tour of what I can do"),
                "find",
            ),
            _lens_prompt(
                "generic_create_document",
                _("Help me create a new document"),
                _("Guided, step by step"),
                "do",
            ),
            _lens_prompt(
                "generic_recent_updates",
                _("Show me recent updates in the system"),
                _("What changed while you were away"),
                "see",
            ),
            _lens_prompt(
                "generic_explain_frappe",
                _("Explain Frappe ERP to me"),
                _("The lay of the land"),
                "find",
            ),
        ],
    }


def _role_bucket_prompts(roles, installed_apps=None):
    """Default prompts matched to the user's lenses, round-robin across
    matched lenses, generic filler last. Pure — roles and installed apps come
    in as lists (apps default to the site's installed apps)."""
    if installed_apps is None:
        installed_apps = frappe.get_installed_apps()
    starters = _lens_starters()
    matched = resolve_lenses(list(roles or []), installed_apps)

    result = []
    queues = [list(starters[lens]) for lens in matched]
    while any(queues):
        for q in queues:
            if q:
                result.append(q.pop(0))
    role_count = len(result)
    result.extend(starters["generic"])

    return [
        {
            "name": p["name"],
            "description": p["description"],
            "subtext": p.get("subtext"),
            "kind": p["kind"],
            "has_arguments": False,
            "source": "role" if index < role_count else "default",
        }
        for index, p in enumerate(result)
    ]


def _get_default_prompts(context):
    """Page asks (Form/List only) followed by the role starters, so the
    landing grid can always backfill to four tiles."""
    page_asks = page_asks_for(context.get("type", "General"), context.get("doctype"))
    return page_asks + _role_bucket_prompts(frappe.get_roles(frappe.session.user))


SUGGESTIONS_CAP = 12
STARTER_SOURCES = ("role", "default")


def _cap_prompts(prompts_list: list[dict], cap: int) -> list[dict]:
    """Keep at most ``cap`` prompts, in order, without dropping the page asks or the
    first role or generic starter of each kind: templates are unbounded and would otherwise push both out."""
    if len(prompts_list) <= cap:
        return prompts_list
    protected: set[int] = set()
    kinds_seen: set[str] = set()
    for index, prompt in enumerate(prompts_list):
        kind = prompt.get("kind")
        if prompt.get("source") == "page":
            protected.add(index)
        elif kind and prompt.get("source") in STARTER_SOURCES and kind not in kinds_seen:
            kinds_seen.add(kind)
            protected.add(index)
    kept = set(protected)
    for index in range(len(prompts_list)):
        if len(kept) >= cap:
            break
        kept.add(index)
    return [prompt for index, prompt in enumerate(prompts_list) if index in kept]


@frappe.whitelist(methods=["GET"])
def get_suggested_prompts(context: str | None = None):
    """
    Get suggested prompts merged from these sources, in emission order:
    1. Curated suggestions (served from FAC's 24h cache, LLM-generated in the background) —
       emitted first so the result[:12] cap can never truncate them out
    2. Pinned templates (user explicit pins)
    3. Context-aware templates (from AR MCP, matched locally to current page)
    4. Personalized suggestions (from AR suggestion engine; fallback when curated is empty)

    Each prompt includes a 'source' field: "pinned", "contextual", "personalized", "role" or "default".
    The response also carries `suggestions_disabled` — true when the user has turned off
    the suggestion grid via FAC Chat User Preferences.

    Returns a list of prompt objects with:
    - name: template name or generated ID
    - description: display text
    - has_arguments: whether template needs input
    - arguments: list of argument definitions (if any)
    - source: "pinned", "contextual", "personalized", "role" or "default"
    """
    try:
        if isinstance(context, str):
            context = json.loads(context) if context else {}

        show_grid = True
        show_personalized = True
        try:
            home_prefs = load_home_preferences(frappe.session.user)
            show_grid = home_prefs["show_suggested_prompts"]
            show_personalized = home_prefs["show_personalized_suggestions"]
        except Exception:
            # Fail closed on the AI-spending part: an unreadable preference must not trigger generation.
            show_grid = True
            show_personalized = False

        result = []
        seen_descriptions = set()

        # === Source 0 (curated): served ONLY from FAC's 24h cache — never
        # blocks on AR. Emitted first so the result[:12] cap below can never
        # truncate it out once templates are appended ===
        curated_emitted = False
        if show_grid and show_personalized:
            try:
                from frappe_assistant_core.chat.api.curated import (
                    curated_row_name,
                    get_cached_curated,
                    schedule_regeneration_if_stale,
                )

                for c in get_cached_curated(frappe.session.user):
                    text = (c.get("text") or "").strip()
                    if not text or text.lower() in seen_descriptions:
                        continue
                    result.append(
                        {
                            "name": curated_row_name(text),
                            "description": text,
                            "subtext": c.get("subtext") or "",
                            "category": c.get("category") or "general",
                            "has_arguments": False,
                            "source": "personalized",
                        }
                    )
                    seen_descriptions.add(text.lower())
                    curated_emitted = True
                schedule_regeneration_if_stale(frappe.session.user)
            except Exception:
                frappe.log_error(
                    title="Curated suggestions read failed",
                    message=frappe.get_traceback(),
                )

        # === Source 1 + 2: Templates from AR (pinned + context-matched) ===
        template_suggestions, raw_templates = _get_template_suggestions(context or {})
        for t in template_suggestions:
            if t["description"].lower() in seen_descriptions:
                continue
            result.append(t)
            seen_descriptions.add(t["description"].lower())

        # === Source 3: Personalized from AR suggestion engine — fallback
        # only when the curated cache had nothing to offer yet ===
        if show_grid and show_personalized and not curated_emitted:
            try:
                from frappe_assistant_core.chat.fac_cloud_client import get_fac_cloud_client

                client = get_fac_cloud_client()
                if client:
                    ar_suggestions = client.get_suggestions(
                        user_id=_ar_user_id(frappe.session.user), context=context or {}, limit=5, timeout=8
                    )
                    if ar_suggestions and ar_suggestions.get("suggestions"):
                        for s in ar_suggestions["suggestions"]:
                            text = s.get("text", "").strip()
                            if text and text.lower() not in seen_descriptions:
                                result.append(
                                    {
                                        "name": f"personalized_{hash(text) & 0xFFFFFF:06x}",
                                        "description": text,
                                        "has_arguments": False,
                                        "source": "personalized",
                                    }
                                )
                                seen_descriptions.add(text.lower())
            except Exception:
                frappe.log_error(
                    title="AR personalized suggestions failed",
                    message=frappe.get_traceback(),
                )

        # === Always append role-aware defaults so the landing grid can
        # backfill to 4 tiles even when smarter sources return 1-3 items ===
        for p in _get_default_prompts(context or {}):
            if p["description"].lower() not in seen_descriptions:
                result.append(p)
                seen_descriptions.add(p["description"].lower())

        result = _cap_prompts(result, SUGGESTIONS_CAP)

        # Return suggestions + raw template data for frontend templateStore hydration.
        # This eliminates the need for a separate get_prompt_templates call.
        return {
            "suggestions": result if show_grid else [],
            "suggestions_disabled": not show_grid,
            "templates": raw_templates,
        }

    except Exception as e:
        frappe.log_error(title="FACO Prompts Error", message=f"Error getting suggested prompts: {e!s}")
        return {
            "suggestions": [
                {
                    "name": "help",
                    "description": "How can I help you?",
                    "has_arguments": False,
                    "source": "default",
                }
            ],
            "suggestions_disabled": False,
            "templates": {"templates": [], "categories": [], "pinned": []},
        }


@frappe.whitelist(methods=["GET"])
def get_prompt_templates():
    """
    Get available MCP prompt templates from AR.

    Returns all templates with user's pinned list.
    MCP server source is hidden for simplicity.

    Returns:
            dict: {
                    "templates": [...],
                    "categories": [...],
                    "pinned": [...]
            }
    """
    try:
        from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
            FACChatUserPreferences,
        )
        from frappe_assistant_core.chat.fac_cloud_client import (
            ARAuthenticationError,
            get_fac_cloud_client,
        )

        client = get_fac_cloud_client()
        if not client:
            return {
                "templates": [],
                "categories": [],
                "pinned": [],
                "error": "Not registered with FAC Cloud",
            }

        frappe_user = frappe.session.user
        ar_user_id = _ar_user_id(frappe_user)

        # Fetch templates with reactive retry on auth failure.
        # Recovery only works for existing users — never auto-registers new ones.
        # AR calls key on the email; _do_user_recovery gets the Frappe docname.
        catalog_cache_key = f"{_CATALOG_CACHE_PREFIX}{ar_user_id}"
        try:
            result = frappe.cache.get_value(catalog_cache_key)
            if result is None:
                result = client.list_prompts(user_id=ar_user_id, timeout=8)
                frappe.cache.set_value(catalog_cache_key, result, expires_in_sec=_CATALOG_CACHE_TTL)
        except ARAuthenticationError:
            try:
                _do_user_recovery(client, frappe_user)
                result = client.list_prompts(user_id=ar_user_id, timeout=8)
            except (frappe.AuthenticationError, Exception):
                # `_do_user_recovery` may have queued a server message via
                # `frappe.throw(...)` before we caught it here. The empty
                # template list is a valid fallback — don't surface a
                # misleading "Couldn't reach AR" toast for what is a
                # silent best-effort recovery attempt. Log to the audit
                # log instead so admins can still trace the failure.
                frappe.clear_messages()
                frappe.local.message_log = []
                return {"templates": [], "categories": [], "pinned": []}

        if not result or not result.get("prompts"):
            return {"templates": [], "categories": [], "pinned": []}

        templates = result.get("prompts", [])

        # Extract unique categories
        categories = list(set(t.get("category", "general") for t in templates if t.get("category")))
        categories.sort()

        # Get user's pinned templates.
        # getattr fallback handles instances where the DocType migration adding
        # `pinned_prompt_templates` hasn't run yet — better to return [] than crash.
        prefs = FACChatUserPreferences.get_or_create_preferences()
        pinned_json = getattr(prefs, "pinned_prompt_templates", None) or "[]"
        try:
            pinned = json.loads(pinned_json) if isinstance(pinned_json, str) else pinned_json
        except json.JSONDecodeError:
            pinned = []

        return {"templates": templates, "categories": categories, "pinned": pinned or []}

    except Exception as e:
        frappe.log_error(title="FACO Templates Error", message=f"Error getting prompt templates: {e!s}")
        return {
            "templates": [],
            "categories": [],
            "pinned": [],
            "error": _safe_error(e, "FACO Templates Error"),
        }


@frappe.whitelist(methods=["POST"])
def update_pinned_templates(pinned_templates: str | list):
    """
    Update user's pinned prompt templates.

    Args:
            pinned_templates: JSON string or list of template names (max 5)

    Returns:
            dict: {"success": bool, "pinned": [...]}
    """
    try:
        from frappe_assistant_core.chat.doctype.fac_chat_user_preferences.fac_chat_user_preferences import (
            FACChatUserPreferences,
        )

        # Parse if string
        if isinstance(pinned_templates, str):
            try:
                pinned_templates = json.loads(pinned_templates)
            except json.JSONDecodeError:
                return {"success": False, "error": "Invalid JSON format"}

        # Validate - should be a list of strings
        if not isinstance(pinned_templates, list):
            return {"success": False, "error": "Expected a list of template names"}

        # Validate each item is a string
        pinned_templates = [str(t) for t in pinned_templates if t]

        # Limit to 5 pinned templates
        if len(pinned_templates) > 5:
            pinned_templates = pinned_templates[:5]

        # Save to user preferences
        prefs = FACChatUserPreferences.get_or_create_preferences()
        prefs.pinned_prompt_templates = json.dumps(pinned_templates)
        prefs.save(ignore_permissions=True)

        return {"success": True, "pinned": pinned_templates}

    except Exception as e:
        frappe.log_error(title="FACO Templates Error", message=f"Error updating pinned templates: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Templates Error")}


@frappe.whitelist(methods=["GET"])
def get_rendered_prompt(prompt_name: str, arguments: str | None = None):
    """
    Get a rendered prompt from AR to use as a message.

    Args:
            prompt_name: The template identifier (e.g., "sales_analysis")
            arguments: Optional JSON string or dict of argument values

    Returns:
            dict: {
                    "success": bool,
                    "prompt": "rendered prompt text",
                    "description": "template description"
            }
    """
    try:
        from frappe_assistant_core.chat.fac_cloud_client import (
            ARAuthenticationError,
            get_fac_cloud_client,
        )

        if not prompt_name:
            return {"success": False, "error": "prompt_name is required"}

        # Parse arguments if string
        if isinstance(arguments, str) and arguments:
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return {"success": False, "error": "Invalid JSON format for arguments"}

        client = get_fac_cloud_client()
        if not client:
            return {"success": False, "error": "Not registered with FAC Cloud"}

        frappe_user = frappe.session.user
        ar_user_id = _ar_user_id(frappe_user)

        # Check user is registered (does NOT auto-register new users).
        # _ensure_user_registered takes the Frappe docname (normalizes internally).
        reg_status = _ensure_user_registered(client, frappe_user)
        if isinstance(reg_status, dict) and reg_status.get("needs_admin"):
            return {
                "success": False,
                "error": "Your account has not been set up yet. Ask your admin to add you from Settings > Users.",
            }

        # Get rendered prompt from AR (with reactive retry on auth failure)
        try:
            result = client.get_prompt(
                prompt_name=prompt_name,
                user_id=ar_user_id,
                arguments=arguments or {},
            )
        except ARAuthenticationError:
            try:
                _do_user_recovery(client, frappe_user)
                result = client.get_prompt(
                    prompt_name=prompt_name,
                    user_id=ar_user_id,
                    arguments=arguments or {},
                )
            except (frappe.AuthenticationError, Exception):
                # See get_prompt_templates: clear any toast queued by the
                # inner `frappe.throw(...)` in `_do_user_recovery`. The
                # caller already gets a structured `{success: false}`
                # response with a precise inline error.
                frappe.clear_messages()
                frappe.local.message_log = []
                return {
                    "success": False,
                    "error": "Your account has not been set up. Ask your admin to add you.",
                }

        if not result:
            return {"success": False, "error": "Failed to get prompt from AR"}

        # Extract the prompt text from the messages
        messages = result.get("messages", [])
        prompt_text = ""

        for msg in messages:
            content = msg.get("content", {})
            if isinstance(content, dict):
                prompt_text += content.get("text", "")
            elif isinstance(content, str):
                prompt_text += content

        if not prompt_text:
            # Fallback to description if no messages
            prompt_text = result.get("description", f"Run {prompt_name} analysis")

        return {"success": True, "prompt": prompt_text.strip(), "description": result.get("description", "")}

    except Exception as e:
        frappe.log_error(title="FACO Templates Error", message=f"Error getting rendered prompt: {e!s}")
        return {"success": False, "error": _safe_error(e, "FACO Templates Error")}
