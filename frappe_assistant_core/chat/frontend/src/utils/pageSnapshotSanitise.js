/**
 * A personal page's rendered markup, made safe to draw on this site's own origin.
 *
 * The markup comes out of the page's sandboxed frame, so the page's script wrote it. Drawn in a
 * host frame for FACO's picture (html2canvas runs in this window, whose requests no frame policy
 * governs) or for Download PDF, any URL left in it could carry the page's data to another server.
 * So every URL that is not this site's /files/ or /assets/, a fragment, or a data: image is removed
 * from attributes, from style attributes and from style elements, before anything draws it.
 */

// Elements that load, embed or run something, or change how the rest is read.
const DROP_TAGS = new Set([
	"script",
	"noscript",
	"link",
	"meta",
	"base",
	"iframe",
	"frame",
	"frameset",
	"object",
	"embed",
	"applet",
	"portal",
	"audio",
	"video",
	"source",
	"track",
	"template",
]);

// Attributes whose value is a URL, or a list of them.
const URL_ATTRS = new Set([
	"src",
	"href",
	"xlink:href",
	"poster",
	"background",
	"action",
	"formaction",
	"data",
	"cite",
	"longdesc",
	"lowsrc",
	"dynsrc",
	"ping",
	"codebase",
	"archive",
	"manifest",
	"icon",
	"profile",
	"usemap",
	"itemtype",
]);
const URL_LIST_ATTRS = new Set(["srcset", "imagesrcset"]);

// CSS that names a resource without url(), or does so in a way this check does not follow.
const CSS_RISKY = /image-set\(|image\(|cross-fade\(|element\(|\\|@import|expression\(/i;
const CSS_URL = /url\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|([^)"'\s]*))\s*\)/gi;
// A browser ignores whitespace and control characters at the start of a URL and in its scheme.
const strip = (value) => String(value).replace(/[\u0000-\u0020]/g, "");

/** Whether a URL stays on this site's public paths, inside the document, or is a data: image. */
export function isSiteUrl(value, origin) {
	const raw = String(value ?? "").trim();
	if (!raw) return true;
	if (raw.startsWith("#")) return true;
	const compact = strip(raw).toLowerCase();
	if (compact.startsWith("data:image/") || compact.startsWith("blob:")) return true;
	let url;
	try {
		url = new URL(raw, `${origin}/`);
	} catch {
		return false;
	}
	return url.origin === origin && (url.pathname.startsWith("/files/") || url.pathname.startsWith("/assets/"));
}

/** Whether a CSS value may stay: every url() in it is a site URL, and it uses no other resource syntax. */
export function isSiteCss(value, origin) {
	const text = String(value ?? "");
	if (CSS_RISKY.test(text)) return false;
	for (const match of text.matchAll(CSS_URL)) {
		if (!isSiteUrl(match[1] ?? match[2] ?? match[3] ?? "", origin)) return false;
	}
	return true;
}

function cleanDeclarations(style, origin) {
	for (const property of Array.from(style)) {
		if (!isSiteCss(style.getPropertyValue(property), origin)) style.removeProperty(property);
	}
}

// The rule types kept: their declarations are checked and their nested rules walked. Anything else
// (@import, @font-face, @namespace, @page, @scope, @property and whatever comes next) is deleted.
const KEPT_RULES = new Set([
	"CSSStyleRule",
	"CSSNestedDeclarations",
	"CSSMediaRule",
	"CSSSupportsRule",
	"CSSKeyframesRule",
	"CSSKeyframeRule",
	"CSSLayerBlockRule",
	"CSSContainerRule",
]);

export function cleanRules(list, origin) {
	for (let i = list.cssRules.length - 1; i >= 0; i--) {
		const rule = list.cssRules[i];
		if (!KEPT_RULES.has(rule.constructor?.name)) {
			list.deleteRule(i);
			continue;
		}
		if (rule.style) cleanDeclarations(rule.style, origin);
		// A style rule holds nested rules too (CSS nesting); they are checked the same way.
		if (rule.cssRules?.length) cleanRules(rule, origin);
	}
}

// The last net over the text a style element ends with: no "<", which could end the element when
// the markup is parsed again, and no url() that is not the site's.
export function finalCss(text, origin) {
	const safe = text.replace(/</g, "\\3c ");
	for (const match of safe.matchAll(CSS_URL)) {
		if (!isSiteUrl(match[1] ?? match[2] ?? match[3] ?? "", origin)) return "";
	}
	return /image-set\(|@import|@font-face/i.test(safe) ? "" : safe;
}

// The style element's text parsed as the browser parses it: a constructable sheet (which drops
// @import itself), or the element's own sheet. Null when neither is available.
function parseSheet(element) {
	try {
		const sheet = new CSSStyleSheet();
		sheet.replaceSync(element.textContent || "");
		return sheet;
	} catch {
		return element.sheet || null;
	}
}

function cleanStyleElement(element, origin) {
	const sheet = parseSheet(element);
	// Nothing parsed means nothing checkable: drop the element.
	if (!sheet) return element.remove();
	cleanRules(sheet, origin);
	element.textContent = finalCss(Array.from(sheet.cssRules, (rule) => rule.cssText).join("\n"), origin);
}

function cleanAttributes(element, origin) {
	for (const { name, value } of Array.from(element.attributes)) {
		const attribute = name.toLowerCase();
		if (attribute.startsWith("on")) element.removeAttribute(name);
		else if (attribute === "style") continue;
		else if (URL_ATTRS.has(attribute)) {
			if (!isSiteUrl(value, origin)) element.removeAttribute(name);
		} else if (URL_LIST_ATTRS.has(attribute)) {
			const candidates = value.split(",").map((candidate) => candidate.trim().split(/\s+/)[0]);
			if (/data:/i.test(value) || !candidates.every((url) => isSiteUrl(url, origin))) element.removeAttribute(name);
		} else if (/url\(|\\/i.test(value) && !isSiteCss(value, origin)) {
			// SVG presentation attributes such as fill or filter can name a resource too.
			element.removeAttribute(name);
		}
	}
	if (element.hasAttribute("style")) {
		cleanDeclarations(element.style, origin);
		if (element.style.length) element.setAttribute("style", element.style.cssText);
		else element.removeAttribute("style");
	}
}

function cleanOnce(html, origin) {
	const doc = new DOMParser().parseFromString(`<!doctype html><html><head></head><body>${html || ""}</body></html>`, "text/html");
	for (const element of Array.from(doc.body.querySelectorAll("*"))) {
		if (!element.isConnected) continue;
		if (DROP_TAGS.has(element.localName)) element.remove();
	}
	for (const element of Array.from(doc.body.querySelectorAll("style"))) cleanStyleElement(element, origin);
	for (const element of Array.from(doc.body.querySelectorAll("*"))) cleanAttributes(element, origin);
	return doc.body.innerHTML;
}

// Cleaning its own output must change nothing; markup that keeps changing on a re-parse is
// relying on a parse difference, and is dropped.
const MAX_PASSES = 3;

/**
 * The markup with every off-site URL removed. Parsed with DOMParser, whose document runs nothing
 * and loads nothing, and cleaned until a pass changes nothing.
 *
 * @param {string} html the page's rendered markup
 * @param {string} [origin] this site's origin
 * @returns {string} the body's markup, cleaned
 */
export function cleanSnapshot(html, origin = window.location.origin) {
	let out = cleanOnce(html, origin);
	for (let pass = 1; pass < MAX_PASSES; pass++) {
		const again = cleanOnce(out, origin);
		if (again === out) return out;
		out = again;
	}
	return "";
}
