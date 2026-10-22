/**
 * Shared markdown rendering with deferred syntax highlighting.
 *
 * `marked` is configured once with a highlighter hook that returns the raw
 * escaped code on first call (so initial render is instant) and triggers
 * an async import of `highlight.js`. After hljs loads, callers can rerun
 * the render to get a highlighted result.
 *
 * The component opts in by calling `ensureHljs()` and re-rendering once it
 * resolves — see MessageBubble / MessageBlockRenderer for the pattern.
 *
 * This keeps ~50 kB of hljs out of the eager chat bundle for the (common)
 * case where a message has no fenced code blocks.
 */

import { marked } from "marked";
import { markedHighlight } from "marked-highlight";
import DOMPurify from "dompurify";
import { localizeSiteLink } from "./siteLinks";

let hljsPromise = null;
let hljs = null;

export function ensureHljs() {
	if (hljs) return Promise.resolve(hljs);
	if (!hljsPromise) {
		hljsPromise = import("./highlight.js").then((mod) => {
			hljs = mod.default || mod;
			return hljs;
		});
	}
	return hljsPromise;
}

function escapeHtml(s) {
	return s
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
}

/**
 * Highlighted HTML for a fenced block, or the escaped code when highlight.js
 * has not loaded yet or does not know the language. No auto-detection: with a
 * trimmed language set it guesses wrong more often than it helps.
 */
export function highlightCode(code, lang) {
	if (hljs && lang && hljs.getLanguage(lang)) {
		return hljs.highlight(code, { language: lang }).value;
	}
	return escapeHtml(code);
}

const NOWRAP_MAX = 40;

const NUMERIC_CELL = /^[-+(]?[₹$€£¥]?\s?\d[\d,]*(\.\d+)?\s?%?\)?$/;

// Decoded text, so an entity does not count as several characters. Empty with no DOM
// (SSR/worker), which leaves the cell unclassed: wrapping, in the message font.
function cellText(html) {
	if (typeof DOMParser === "undefined") return "";
	return (new DOMParser().parseFromString(html, "text/html").body.textContent || "").trim();
}

// md-nowrap: one token (an invoice number, a date, an amount) is unreadable once the browser
// breaks it at a hyphen; prose cells may wrap. md-num: a figure keeps the tabular monospace so a
// column aligns on the digit; every other cell reads in the message font.
function cellClasses(html) {
	const text = cellText(html);
	const classes = [];
	if (text.length > 0 && text.length <= NOWRAP_MAX && !/\s/.test(text)) classes.push("md-nowrap");
	if (NUMERIC_CELL.test(text)) classes.push("md-num");
	return classes.length ? ` class="${classes.join(" ")}"` : "";
}

const tableRenderer = {
	table(header, body) {
		const tbody = body ? `<tbody>${body}</tbody>` : "";
		return `<div class="md-table-scroll"><table><thead>${header}</thead>${tbody}</table></div>\n`;
	},
	tablecell(content, flags) {
		const tag = flags.header ? "th" : "td";
		const align = flags.align ? ` align="${flags.align}"` : "";
		return `<${tag}${align}${cellClasses(content)}>${content}</${tag}>\n`;
	},
};

let configured = false;
function configure() {
	if (configured) return;
	configured = true;
	// marked 5+ dropped the `highlight` option; it is silently ignored by
	// setOptions, which is how FAC Chat shipped with no highlighting at all.
	marked.use(
		markedHighlight({
			langPrefix: "hljs language-",
			highlight: (code, lang) => highlightCode(code, lang),
		})
	);
	marked.use({
		breaks: true,
		gfm: true,
		renderer: tableRenderer,
		walkTokens(token) {
			if (token.type === "link") token.href = localizeSiteLink(token.href);
		},
	});
}

/**
 * Render markdown to sanitized HTML. Code blocks are escaped (no syntax
 * highlighting) until `ensureHljs()` resolves; after that, subsequent calls
 * highlight as normal. DOMPurify's defaults allow <img> — chat messages
 * need it (attachments, generated charts).
 */
export function renderMarkdown(content) {
	configure();
	return DOMPurify.sanitize(marked.parse(content));
}

/**
 * Same rendering, but strips <img> entirely rather than just its event
 * handlers. For platform notifications — admin-authored content crossing a
 * tenant boundary, where an <img src> is a tracking-pixel/content-injection
 * vector, not a feature. Do not use this for chat message rendering.
 *
 * assistant_runtime_admin's NotificationPreviewBanner.vue duplicates this
 * sanitize config (separate package, can't import this file) to preview
 * notifications as tenants will actually see them. Changing the config here
 * without updating that file re-breaks the preview.
 */
export function renderNotificationMarkdown(content) {
	configure();
	return DOMPurify.sanitize(marked.parse(content), { FORBID_TAGS: ["img"] });
}
