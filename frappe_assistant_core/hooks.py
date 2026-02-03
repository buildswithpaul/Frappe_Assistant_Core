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

from . import __version__ as app_version

app_name = "frappe_assistant_core"
app_title = "Frappe Assistant Core"
app_publisher = "Paul Clinton"
app_description = "AI Assistant integration core for Frappe Framework"
app_icon = "octicon octicon-server"
app_color = "blue"
app_email = "jypaulclinton@gmail.com"
app_license = "AGPL-3.0"
app_version = app_version

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/frappe_assistant_core/css/frappe_assistant_core.css"
# app_include_js = "/assets/frappe_assistant_core/js/frappe_assistant_core.js"

# include js, css files in header of web template
# web_include_css = "/assets/frappe_assistant_core/css/frappe_assistant_core.css"
# web_include_js = "/assets/frappe_assistant_core/js/frappe_assistant_core.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "frappe_assistant_core/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# "Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jenv = {
    "methods": [
        "frappe_assistant_core.utils.template_helpers.get_assistant_status",
        "frappe_assistant_core.utils.template_helpers.get_tool_count",
    ]
}

# Installation
# ------------

# before_install hooks can be added here if needed


# after_install = "frappe_assistant_core.utils.migration_hooks.after_install"

after_install = [
    "frappe_assistant_core.utils.migration_hooks.after_install",
    "frappe_assistant_core.utils.email_invite.send_fac_admin_invite",
]


# Uninstallation
# ------------

# before_uninstall = "frappe_assistant_core.uninstall.before_uninstall"
after_uninstall = "frappe_assistant_core.utils.migration_hooks.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "frappe_assistant_core.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "Assistant Audit Log": "frappe_assistant_core.utils.permissions.get_audit_permission_query_conditions",
    "Prompt Template": "frappe_assistant_core.utils.permissions.get_prompt_permission_query_conditions",
}

# has_permission = {
# "Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# "ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "*": {
        "on_update": "frappe_assistant_core.utils.audit_trail.log_document_change",
        "on_submit": "frappe_assistant_core.utils.audit_trail.log_document_submit",
        "on_cancel": "frappe_assistant_core.utils.audit_trail.log_document_cancel",
    },
    "Assistant Core Settings": {"on_update": "frappe_assistant_core.utils.cache.invalidate_settings_cache"},
    "Assistant Audit Log": {"after_insert": "frappe_assistant_core.utils.cache.invalidate_dashboard_cache"},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "cron": {
        "0 0 * * *": ["frappe_assistant_core.assistant_core.server.cleanup_old_logs"],
        "*/30 * * * *": ["frappe_assistant_core.utils.cache.warm_cache"],
    },
    # Hourly tasks removed - no longer needed after Assistant Connection Log removal
}

# Testing
# -------

# before_tests = "frappe_assistant_core.install.before_tests"

# Overriding Methods
# ------------------------------
#
# Override Frappe's OAuth endpoints
# - openid_configuration: Add MCP-required fields
# - get_token: Properly handle Basic auth for client authentication
override_whitelisted_methods = {
    "frappe.integrations.oauth2.openid_configuration": "frappe_assistant_core.api.oauth_discovery.openid_configuration",
    "frappe.integrations.oauth2.get_token": "frappe_assistant_core.api.oauth_token.get_token",
}

# Custom Page Renderers
# ----------------------

# Handle .well-known OAuth endpoints with custom renderer
page_renderer = ["frappe_assistant_core.api.oauth_wellknown_renderer.WellKnownRenderer"]

#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# "Task": "frappe_assistant_core.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]


# User Data Protection
# --------------------

# user_data_fields = [
# {
# "doctype": "{doctype_1}",
# "filter_by": "{filter_by}",
# "redact_fields": ["{field_1}", "{field_2}"],
# "partial": 1,
# },
# {
# "doctype": "{doctype_2}",
# "filter_by": "{filter_by}",
# "partial": 1,
# },
# {
# "doctype": "{doctype_3}",
# "strict": False,
# },
# {
# "doctype": "{doctype_4}"
# }
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# "frappe_assistant_core.auth.validate"
# ]

# Request Hooks
# -------------

# Handle CORS for OAuth endpoints (dynamic client registration, token endpoints, etc.)
# Sets frappe.conf.allow_cors (V15) and frappe.local.allow_cors (V16+) based on
# "Allowed Public Client Origins" setting - works immediately without restart
before_request = ["frappe_assistant_core.api.oauth_cors.set_cors_for_oauth_endpoints"]

# Automatically update python controller files with type annotations for DocTypes
# Use Developer Mode in Bench set up to auto append type annotation
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# "Logging DocType Name": 30  # days to retain logs
# }

# Standard Roles
# ---------------

standard_roles = [
    {"role": "Assistant User", "role_color": "#3498db"},
    {"role": "Assistant Admin", "role_color": "#e74c3c"},
]

# Boot
# -----

# boot_session = "frappe_assistant_core.boot.boot_session"

# Startup
# -------

app_startup = "frappe_assistant_core.startup.startup"
before_migrate = "frappe_assistant_core.utils.migration_hooks.before_migrate"
after_migrate = [
    "frappe_assistant_core.startup.startup",
    "frappe_assistant_core.utils.migration_hooks.after_migrate",
]

# Fixtures
# --------

fixtures = [
    {"doctype": "Custom Field", "filters": {"dt": "User", "fieldname": ["in", ["assistant_enabled"]]}},
    {"doctype": "Role", "filters": {"role_name": ["in", ["Assistant User", "Assistant Admin"]]}},
    # System prompt templates - these are installed via after_migrate hook
    # because they require special handling for child table data (arguments)
]

# Enhanced Plugin Architecture
# ----------------------------

# Tool discovery from external apps via hooks
assistant_tools = [
    # Core tools are discovered automatically from plugins
]

# Tool configuration overrides
assistant_tool_configs = {
    # Example tool config:
    # "document_create": {
    #     "max_batch_size": 100,
    #     "timeout": 30
    # }
}
