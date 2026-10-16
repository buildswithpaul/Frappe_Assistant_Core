# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""
A message tool's body, sent the way its approval card shows it.

The card renders a plain-text body with each newline as a line break. Frappe's mail path would
instead run plain text through markdown (``email_body.get_email``, and Helpdesk's
``as_markdown=True``), which folds the lines into one paragraph and turns ``*x*`` into emphasis.
Converting here, with the same rule as the card's ``renderMessageBody``, keeps card, email and
ticket thread the same.
"""

import html
import re

_LOOKS_LIKE_HTML = re.compile(r"<[a-z][\s\S]*>", re.IGNORECASE | re.ASCII)


def as_html_body(text: str) -> str:
    """Escape a plain-text body and keep its line breaks; leave HTML as it is. Wrapped in a block
    element, which markdown leaves untouched, so ``*x*`` is not turned into emphasis."""
    text = text or ""
    if not _LOOKS_LIKE_HTML.search(text):
        text = html.escape(text, quote=False).replace("\n", "<br>")
    return f"<div>{text}</div>"
