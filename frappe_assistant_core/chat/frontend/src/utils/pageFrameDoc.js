/**
 * The document a personal page ("Only me") runs in: its own html, style and script, with no way to
 * act as the user and no ordinary way to reach another server.
 *
 * Two frames, both `sandbox="allow-scripts"` and nothing else, so each has an opaque origin: no
 * cookies, no CSRF token, no access to the chat or Desk around it, no forms, popups or top
 * navigation. The outer frame runs nothing; its policy's `frame-src 'none'` stops the inner frame
 * navigating itself to another server with data in the URL, which a single sandboxed frame may do.
 * The inner frame holds the page. Its script reads data only through the host's bridge
 * (pageFrameHost.js), which serves Frappe's own reads as the user and asks the user before
 * anything else.
 *
 * What is still possible: a deliberately malicious script can leak small amounts through DNS
 * lookups or timing side channels, which no browser policy closes. The runtime removes WebRTC and
 * DNS prefetching is off, which narrows this; it does not seal it.
 */

/** The only sandbox flag either frame gets. */
export const PAGE_FRAME_SANDBOX = "allow-scripts";

const ASSETS = "/assets/frappe_assistant_core/js/";

/** The frame runtime and the chart bundle, both built by `npm run build` into public/js. */
export const pageFrameRuntimeUrl = (origin, version = "") => `${origin}${ASSETS}fac_page_frame.js?v=${version}`;
export const pageFrameChartsUrl = (origin, version = "") => `${origin}${ASSETS}fac_page_charts.js?v=${version}`;

/**
 * Both frames' policy. The inner frame inherits the outer one's and adds its own copy, so each
 * directive here is the most either may do: scripts only with this render's nonce or from FAC's
 * own built bundles, images and fonts from the site's public paths, and no fetch, socket or frame.
 */
export function pageFrameCsp(origin, nonce) {
	const site = (path) => `${origin}${path}`;
	return [
		"default-src 'none'",
		`script-src 'nonce-${nonce}' ${site(ASSETS)}`,
		"style-src 'unsafe-inline'",
		`img-src ${site("/files/")} ${site("/assets/")} data: blob:`,
		`font-src ${site("/assets/")} data:`,
		"connect-src 'none'",
		// No child realm can exist, whatever the JavaScript hardening misses.
		"frame-src 'none'",
		"child-src 'none'",
		"object-src 'none'",
		"form-action 'none'",
		"base-uri 'none'",
	].join("; ");
}

/** A fresh nonce per render, so a page cannot reuse one it saw in an earlier version. */
export function makeNonce() {
	const bytes = new Uint8Array(16);
	crypto.getRandomValues(bytes);
	return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

// No hint in the page's markup starts a DNS lookup of a name it chose.
const NO_DNS_PREFETCH = '<meta http-equiv="x-dns-prefetch-control" content="off">';

const attr = (text) => String(text).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
// Text inside <style> or <script>: a closing tag in it would end the element early.
const inStyle = (css) => String(css || "").replace(/<\/style/gi, "<\\/style");
const inScript = (js) => String(js || "").replace(/<\/script/gi, "<\\/script");
// JSON inside <script type="application/json">: "<" escaped so no tag can close it.
const inJson = (value) => JSON.stringify(value).replace(/</g, "\\u003c");

/**
 * The outer frame's srcdoc.
 *
 * @param {object} parts
 * @param {string} parts.html the page's html, already sanitised by get_page
 * @param {string} parts.style the page's style, already sanitised by get_page
 * @param {string} parts.script the page's script
 * @param {string} parts.kitCss the mockup kit
 * @param {string} parts.user the session user, for frappe.session.user
 * @param {object} [parts.formatSettings] the site's number, currency and date settings, for
 *   frappe.format (get_page's format_settings)
 * @param {string} parts.origin the site origin, e.g. https://erp.example.com
 * @param {string} parts.nonce from makeNonce()
 * @param {string} [parts.version] the build version, so a rebuilt bundle is refetched
 */
export function pageFrameSrcdoc({ html, style, script, kitCss, user, formatSettings, origin, nonce, version = "" }) {
	const csp = `<meta http-equiv="Content-Security-Policy" content="${attr(pageFrameCsp(origin, nonce))}">`;
	// Only a script that names fac can draw a chart, so only such a page loads the bundle.
	const charts = /\bfac\b/.test(script || "")
		? `<script nonce="${nonce}" src="${attr(pageFrameChartsUrl(origin, version))}"></script>`
		: "";
	const config = inJson({ user: user || "", format_settings: formatSettings || {} });
	const inner = [
		"<!doctype html><html><head>",
		csp,
		NO_DNS_PREFETCH,
		'<meta charset="utf-8">',
		`<style>${inStyle(kitCss)}\n${inStyle(style)}\nhtml,body{margin:0;background:#fff}</style>`,
		`<script type="application/json" id="fac-page-config">${config}</script>`,
		`<script nonce="${nonce}" src="${attr(pageFrameRuntimeUrl(origin, version))}"></script>`,
		charts,
		"</head><body>",
		`<div class="fac-page-root">${html || ""}</div>`,
		// The script runs as a function of the same four names the chat panel and Desk give it.
		`<script nonce="${nonce}">window.__fac_page && window.__fac_page.run(function (root_element, frappe, __, fac) {\n`,
		inScript(script),
		"\n});</script>",
		"</body></html>",
	].join("");
	return [
		"<!doctype html><html><head>",
		csp,
		NO_DNS_PREFETCH,
		'<meta charset="utf-8">',
		"<style>html,body{margin:0;height:100%;overflow:hidden}iframe{display:block;width:100%;height:100%;border:0}</style>",
		"</head><body>",
		`<iframe sandbox="${PAGE_FRAME_SANDBOX}" title="page" srcdoc="${attr(inner)}"></iframe>`,
		"</body></html>",
	].join("");
}
