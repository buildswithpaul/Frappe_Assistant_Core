/**
 * Message tools — tools that send a message to someone — and how their approval card reads them.
 *
 * AR pauses these like any write tool; the card shows the draft as a message instead of a
 * field table. Names are exact: AR never prefixes the managed FAC server's tools, so a BYO
 * server's `x_send_email` is not ours. A new channel adds one entry here.
 *
 * Each entry: `sendLabel` for the approve button, `previewArgs(input)` for
 * `get_message_preview`, and `read(input)` → `{ to, cc, subject, body }` from the tool input
 * (`to`/`subject` null when the server preview resolves them).
 */
import DOMPurify from "dompurify";

const list = (value) => (Array.isArray(value) ? value.filter(Boolean) : []);

export const MESSAGE_TOOLS = {
	reply_to_helpdesk_ticket: {
		sendLabel: "Send reply",
		previewArgs: (input) => ({ ticket: input.ticket }),
		read: (input) => ({ to: null, cc: list(input.cc), subject: null, body: input.message || "" }),
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

/**
 * Model-written body → safe HTML. Plain text keeps its line breaks; images are dropped so an
 * approval card never fetches a remote URL the model chose.
 */
export function renderMessageBody(body) {
	const text = String(body || "");
	const html = /<[a-z][\s\S]*>/i.test(text) ? text : escapeText(text);
	return DOMPurify.sanitize(html, { FORBID_TAGS: ["img", "style"] });
}
