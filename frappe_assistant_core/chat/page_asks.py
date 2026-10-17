# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
# AGPL-3.0 License

"""Page-ask templates offered on Form and List pages.

``{doctype}`` and ``{name}`` stay literal in the returned descriptions: the
client fills them in from the page it is on, so the server never needs the
document name. Each template is a lazily translated whole sentence (``_lt``), resolved with
``str()`` at request time so it follows the user's language.
"""

from frappe import _lt

PAGE_ASKS: dict[str, list] = {
    "Sales Invoice": [
        _lt("Why is {doctype} {name} still unpaid?"),
        _lt("Which items drive the value of {doctype} {name}?"),
        _lt("Has this customer paid late before? Check {doctype} {name}"),
        _lt("Draft a payment reminder for {doctype} {name}"),
    ],
    "Purchase Invoice": [
        _lt("When is {doctype} {name} due for payment?"),
        _lt("Does {doctype} {name} match its purchase order and receipt?"),
        _lt("What did we pay this supplier in the last year, given {doctype} {name}?"),
    ],
    "Payment Entry": [
        _lt("Which invoices does {doctype} {name} settle?"),
        _lt("Is anything left unallocated on {doctype} {name}?"),
        _lt("Explain the accounting entries behind {doctype} {name}"),
    ],
    "Sales Order": [
        _lt("What is still to be delivered or billed on {doctype} {name}?"),
        _lt("Is there enough stock to fulfil {doctype} {name}?"),
        _lt("Summarise the history with this customer, starting from {doctype} {name}"),
    ],
    "Purchase Order": [
        _lt("What has been received and billed against {doctype} {name}?"),
        _lt("Is {doctype} {name} running late?"),
        _lt("How do the prices on {doctype} {name} compare with earlier orders?"),
    ],
    "Quotation": [
        _lt("How likely is {doctype} {name} to convert?"),
        _lt("How does {doctype} {name} compare with this customer's past orders?"),
        _lt("Draft a follow-up email for {doctype} {name}"),
    ],
    "Delivery Note": [
        _lt("Has {doctype} {name} been billed?"),
        _lt("Which items on {doctype} {name} are still pending delivery?"),
        _lt("Summarise the order that {doctype} {name} fulfils"),
    ],
    "Customer": [
        _lt("What does {doctype} {name} owe us, and since when?"),
        _lt("Summarise sales to {doctype} {name} over the last year"),
        _lt("How reliably does {doctype} {name} pay?"),
        _lt("Which open orders or quotations does {doctype} {name} have?"),
    ],
    "Supplier": [
        _lt("What do we owe {doctype} {name}, and when is it due?"),
        _lt("Summarise purchases from {doctype} {name} over the last year"),
        _lt("Which open purchase orders does {doctype} {name} have?"),
    ],
    "Item": [
        _lt("How much stock of {doctype} {name} do we have, and where?"),
        _lt("How fast does {doctype} {name} sell?"),
        _lt("Who are the main suppliers of {doctype} {name}?"),
        _lt("Is {doctype} {name} below its reorder level?"),
    ],
    "Lead": [
        _lt("What is the best next step for {doctype} {name}?"),
        _lt("Draft a first outreach email to {doctype} {name}"),
        _lt("Has anyone contacted {doctype} {name} yet?"),
    ],
    "Opportunity": [
        _lt("What is blocking {doctype} {name} from closing?"),
        _lt("Summarise all contact so far on {doctype} {name}"),
        _lt("Draft a follow-up for {doctype} {name}"),
    ],
    "Employee": [
        _lt("How much leave has {doctype} {name} taken this year?"),
        _lt("Summarise the recent attendance of {doctype} {name}"),
        _lt("What approvals are pending for {doctype} {name}?"),
    ],
    "Leave Application": [
        _lt("Does {doctype} {name} clash with anyone else's leave in the team?"),
        _lt("What leave balance is left after {doctype} {name}?"),
        _lt("Summarise the leave history of the applicant on {doctype} {name}"),
    ],
}

GENERIC_FORM_ASKS: list = [
    _lt("Summarise this {doctype}: {name}"),
    _lt("What changed on {doctype} {name} recently?"),
    _lt("Show records related to {doctype} {name}"),
]

LIST_ASKS: list = [
    _lt("Summarise this {doctype} list"),
    _lt("Which of these {doctype} records need attention?"),
]


def _templates_for(context_type: str, doctype: str | None) -> list:
    if not doctype:
        return []
    if context_type == "Form":
        return PAGE_ASKS.get(doctype, GENERIC_FORM_ASKS)
    if context_type == "List":
        return LIST_ASKS
    return []


def page_asks_for(context_type: str, doctype: str | None) -> list[dict]:
    """Translated page-ask templates; ``{doctype}``/``{name}`` are filled client-side."""
    return [
        {
            "name": f"page_ask_{index}",
            "description": str(template),
            "has_arguments": False,
            "source": "page",
        }
        for index, template in enumerate(_templates_for(context_type, doctype), start=1)
    ]
