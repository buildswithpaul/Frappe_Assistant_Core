# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Give every existing chat session a FAC Chat Conversation row.

Before 3.2 a conversation existed only as FAC Chat Message rows sharing a
session_id. New messages maintain the row themselves (FACChatMessage.after_insert);
this fills it in for history, batched so a large message table cannot time out
a migrate. Sessions that already have a row are skipped, so re-running is safe.
"""

import frappe
from frappe.query_builder.functions import Count, Max, Min

from frappe_assistant_core.chat.doctype.fac_chat_conversation.fac_chat_conversation import auto_title


def execute():
    backfill()


def backfill(batch_size: int = 500) -> int:
    FM = frappe.qb.DocType("FAC Chat Message")
    CV = frappe.qb.DocType("FAC Chat Conversation")
    inserted = 0
    last_sid = ""
    while True:
        sessions = (
            frappe.qb.from_(FM)
            .select(
                FM.session_id,
                Max(FM.user).as_("user"),
                Min(FM.creation).as_("started"),
                Max(FM.creation).as_("last_activity"),
                Count(FM.name).as_("message_count"),
                Min(FM.is_archived).as_("is_archived"),
            )
            .where(FM.session_id > last_sid)
            .where(FM.session_id.notin(frappe.qb.from_(CV).select(CV.name)))
            .groupby(FM.session_id)
            .orderby(FM.session_id)
            .limit(batch_size)
        ).run(as_dict=True)
        if not sessions:
            return inserted
        last_sid = sessions[-1].session_id

        titles: dict[str, str] = {}
        for msg in frappe.get_all(
            "FAC Chat Message",
            filters={"session_id": ["in", [s.session_id for s in sessions]], "role": "user"},
            fields=["session_id", "content"],
            order_by="creation asc",
            limit_page_length=0,
        ):
            titles.setdefault(msg.session_id, auto_title(msg.content))

        now = frappe.utils.now()
        frappe.db.bulk_insert(
            "FAC Chat Conversation",
            fields=[
                "name",
                "session_id",
                "user",
                "title",
                "title_is_custom",
                "started",
                "last_activity",
                "message_count",
                "is_archived",
                "owner",
                "modified_by",
                "creation",
                "modified",
            ],
            values=[
                (
                    s.session_id,
                    s.session_id,
                    s.user,
                    titles.get(s.session_id, ""),
                    0,
                    s.started,
                    s.last_activity,
                    s.message_count,
                    s.is_archived,
                    s.user,
                    s.user,
                    now,
                    now,
                )
                for s in sessions
                if s.user
            ],
            ignore_duplicates=True,
        )
        inserted += sum(1 for s in sessions if s.user)
