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
import DOMPurify from "dompurify";

let hljsPromise = null;
let hljs = null;

export function ensureHljs() {
	if (hljs) return Promise.resolve(hljs);
	if (!hljsPromise) {
		hljsPromise = import("highlight.js").then((mod) => {
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

let configured = false;
function configure() {
	if (configured) return;
	configured = true;
	marked.setOptions({
		highlight: (code, lang) => {
			if (hljs) {
				if (lang && hljs.getLanguage(lang)) {
					return hljs.highlight(code, { language: lang }).value;
				}
				return hljs.highlightAuto(code).value;
			}
			// hljs hasn't loaded yet — return escaped code so it renders
			// safely. Caller should ensureHljs() and re-render once ready.
			return escapeHtml(code);
		},
		breaks: true,
		gfm: true,
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
