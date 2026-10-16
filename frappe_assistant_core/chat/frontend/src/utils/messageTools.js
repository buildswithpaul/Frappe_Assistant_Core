/**
 * Message tools — tools that send a message to someone — and how their approval card reads them.
 *
 * AR pauses these like any write tool; the card shows the draft as a message instead of a
 * field table. Names are exact: AR never prefixes the managed FAC server's tools, so a BYO
 * server's `x_send_email` is not ours. A new channel adds one entry here.
 *
 * Each entry: `sendLabel` for the approve button, `previewArgs(input)` for
 * `get_message_preview`, and `read(input)` → `{ to, cc, subject, body }` from the tool input
 * (`to`/`subject` null or empty when the server preview resolves them).
 */
import DOMPurify from "dompurify";

const list = (value) => (Array.isArray(value) ? value.filter(Boolean) : []);

export const MESSAGE_TOOLS = {
	reply_to_helpdesk_ticket: {
		sendLabel: "Send reply",
		previewArgs: (input) => ({ ticket: input.ticket }),
		read: (input) => ({ to: null, cc: list(input.cc), subject: null, body: input.message || "" }),
	},
	send_crm_email: {
		sendLabel: "Send email",
		previewArgs: (input) => ({ doctype: input.doctype, name: input.name }),
		read: (input) => ({
			to: list(input.recipients),
			cc: list(input.cc),
			subject: input.subject || "",
			body: input.message || "",
		}),
	},
	send_email: {
		sendLabel: "Send email",
		previewArgs: () => ({}),
		read: (input) => ({
			to: list(input.recipients),
			cc: list(input.cc),
			subject: input.subject || "",
			body: input.message || "",
		}),
	},
};

export function isMessageTool(name) {
	return Boolean(name) && Object.hasOwn(MESSAGE_TOOLS, name);
}

const escapeText = (text) =>
	text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");

// Formatting only. Anything else could hide text from the card (class, hidden, style) or fetch a
// URL the model chose (img, video poster, svg image), so the preview drops it and says so.
const PREVIEW_TAGS = [
	"p", "br", "a", "b", "strong", "i", "em", "u", "s", "ul", "ol", "li", "blockquote",
	"h1", "h2", "h3", "h4", "table", "thead", "tbody", "tr", "th", "td", "span", "div", "pre", "code", "hr",
];
const PREVIEW_ATTRS = ["href", "colspan", "rowspan"];

// Link text can say anything; show the real address after it.
function revealLinks(html) {
	const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
	for (const link of doc.querySelectorAll("a[href]")) {
		const href = link.getAttribute("href");
		if (link.textContent.trim() !== href) link.after(` (${href})`);
	}
	return doc.body.innerHTML;
}

// DOMPurify reports the parser's own wrappers as removed; they are not part of the email.
const DOCUMENT_WRAPPERS = new Set(["HTML", "HEAD", "BODY"]);

// Each dropped element once, plus attributes dropped from elements the preview kept.
function countDropped(removed) {
	const elements = new Set(
		removed
			.filter((entry) => entry.element && !DOCUMENT_WRAPPERS.has(entry.element.nodeName))
			.map((entry) => entry.element),
	);
	const attributes = removed.filter((entry) => entry.attribute && !elements.has(entry.from));
	return elements.size + attributes.length;
}

/**
 * Model-written body → `{ html, hiddenCount }` for the approval card. Plain text keeps its line
 * breaks. The email itself is sent unchanged, so `hiddenCount` (elements and attributes the
 * preview dropped) lets the card say that part of it is not shown.
 */
export function renderMessageBody(body) {
	const text = String(body || "");
	const source = /<[a-z][\s\S]*>/i.test(text) ? text : escapeText(text);
	const html = DOMPurify.sanitize(source, { ALLOWED_TAGS: PREVIEW_TAGS, ALLOWED_ATTR: PREVIEW_ATTRS });
	return { html: revealLinks(html), hiddenCount: countDropped(DOMPurify.removed) };
}
