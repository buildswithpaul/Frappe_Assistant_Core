import { marked } from "marked";
import DOMPurify from "dompurify";

const MAX_LENGTH = 100;
const FALLBACK = "Thought about the request";
// The header is a button: inline emphasis and code only, never links.
const ALLOWED_TAGS = ["strong", "em", "code", "del"];

// Reasoning summaries open with a title wrapped in emphasis (OpenAI sends
// "**Assessing sales orders**"). The header is already styled as a title,
// so the wrapper is dropped rather than rendered as bold.
const TITLE_MARKERS = ["**", "__", "*", "_"];

function unwrapTitle(line) {
	for (const marker of TITLE_MARKERS) {
		const inner = line.slice(marker.length, -marker.length);
		if (line.startsWith(marker) && line.endsWith(marker) && inner && !inner.includes(marker)) {
			return inner.trim();
		}
	}
	return line;
}

function stripMarkdown(text) {
	return text.replace(/[*_~`]/g, "");
}

function truncate(text) {
	const cut = text.substring(0, MAX_LENGTH);
	const lastSpace = cut.lastIndexOf(" ");
	return (lastSpace > 40 ? cut.substring(0, lastSpace) : cut) + "...";
}

function escapeHtml(text) {
	return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Sanitized inline HTML for a thinking block's collapsed header. */
export function thinkingHeaderHtml(content) {
	let line = (content || "").trim().split("\n")[0].trim();
	line = line.replace(/^#{1,6}\s+/, "");
	line = unwrapTitle(line);
	if (!stripMarkdown(line).trim()) return FALLBACK;

	// Cutting inside a ** or ` pair would show the stray marker, so a long
	// line is shortened as plain text.
	if (line.length > MAX_LENGTH) return escapeHtml(truncate(stripMarkdown(line)));
	return DOMPurify.sanitize(marked.parseInline(line), { ALLOWED_TAGS, ALLOWED_ATTR: [] });
}
