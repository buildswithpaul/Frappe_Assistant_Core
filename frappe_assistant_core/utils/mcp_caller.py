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

"""Identify which client is calling the MCP endpoint.

FAC Cloud is not a privileged inside caller: it reaches this site through the very
same ``fac_endpoint.handle_mcp`` URL that Claude Desktop, ChatGPT and any
self-registered client use — ``chat/api/auth.py`` hands FAC Cloud that URL at
registration time. So "is this FAC Cloud?" has to be answered from the request
itself.

The answer comes from the OAuth client the presented bearer token belongs to.
FAC Cloud authenticates with one pinned, server-created client
(``FAC_CLOUD_OAUTH_CLIENT_ID``); every other MCP client gets a client minted by
dynamic registration with an unpredictable id. That makes the signal
server-side: nothing a client can assert about itself — an ``initialize``
``clientInfo`` string, a header, a user agent — takes part in the decision.
"""

from typing import Optional

import frappe

# The OAuth Client FAC Cloud authenticates with when it calls this site's MCP
# endpoint. Pinned as the docname so that `name == client_id`; see
# `_get_or_create_ar_oauth_client` for why that pinning is load-bearing.
FAC_CLOUD_OAUTH_CLIENT_ID = "fac-cloud-integration"


def presented_bearer_token() -> Optional[str]:
    """The bearer token on this request, or None when it carries no usable one.

    Returns None rather than raising, so a caller authenticated by session cookie
    or API key is simply "not a bearer client" — and so is a caller with no HTTP
    request at all, such as a background job or a bench command, where reading the
    header would otherwise raise.
    """
    try:
        header = frappe.get_request_header("Authorization", "") or ""
    except Exception:
        return None

    scheme, _space, token = header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def request_is_from_fac_cloud() -> bool:
    """Whether FAC Cloud's own OAuth client authenticated this request.

    False for session cookies, API keys and every other OAuth client. Any failure
    to establish the identity also answers False, so the restriction this gates
    fails closed — a tool stays hidden rather than leaking to an unidentified
    caller.
    """
    token = presented_bearer_token()
    if not token:
        return False

    try:
        row = frappe.db.get_value(
            "OAuth Bearer Token",
            {"access_token": token},
            ["client", "user", "status"],
            as_dict=True,
        )
    except Exception:
        return False

    if not row or row.status != "Active" or row.user != frappe.session.user:
        return False

    return row.client == FAC_CLOUD_OAUTH_CLIENT_ID
