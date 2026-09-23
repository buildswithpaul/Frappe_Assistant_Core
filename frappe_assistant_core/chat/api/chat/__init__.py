# Frappe Assistant Core - Chat API package
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Chat streaming, sessions, and message history.

Submodule layout (kept as a package so each topical surface has its
own file, since the original flat module exceeded 1,600 lines):

- ``messages``  — send_message, resume_interrupt, the bounded relay
                  thread pool
- ``relay``     — _relay_ar_stream and _relay_ar_interrupt_resume
                  background-thread bodies
- ``helpers``   — non-whitelisted internal helpers shared by both
                  paths (socket emit, FACO Message persistence,
                  GDPR-restriction check)
- ``sessions``  — list / history / archive / continue endpoints

Every public endpoint and the internal helpers consumed by tests are
re-exported here so the dotted whitelist path
``frappe_assistant_core.chat.api.chat.<func>``
continues to resolve unchanged.

Re-export aggregator: F401 is globally ignored in this app's ruff
config, so no per-line noqa is necessary.
"""

from frappe_assistant_core.chat.api.chat.cancel import (
    cancel_stream,
    is_cancelled,
    mark_cancelled,
)
from frappe_assistant_core.chat.api.chat.cancel import (
    clear as clear_cancel,
)
from frappe_assistant_core.chat.api.chat.helpers import (
    _emit_socket_event,
    _ensure_assistant_msg,
    _extract_file_attachments,
    _find_assistant_msg_by_message_id,
    _is_processing_restricted,
    _log_conversation,
    _log_stream_error_detail,
    _prepare_prompt,
    _update_subscription_cache,
)
from frappe_assistant_core.chat.api.chat.hitl import (
    get_pending_interrupt,
)
from frappe_assistant_core.chat.api.chat.messages import (
    _relay_pool,
    continue_response,
    resume_interrupt,
    send_message,
)
from frappe_assistant_core.chat.api.chat.relay import (
    _relay_ar_interrupt_resume,
    _relay_ar_stream,
)
from frappe_assistant_core.chat.api.chat.sessions import (
    archive_all_conversations,
    archive_session,
    clear_all_conversations,
    continue_archived_session,
    create_session,
    delete_session,
    get_archived_sessions,
    get_session_history,
    get_user_sessions,
)
