// A held FAC Page's html, as the chat panel draws it before the user clicks Run new version.
// get_page already serves a personal page's html through an allowlist; this is the panel's own
// second line, so nothing in the html runs code before then. DOMPurify keeps only allowlisted
// tags and attributes (no inline handlers, srcdoc, script or style); forms and buttons stay,
// because the page's own script may wire them once it runs.
import DOMPurify from "dompurify";

// Its own instance, so the hook below never reaches the chat's markdown sanitising.
const purifier = DOMPurify(window);

// Tags that embed another document, act on the whole one, or animate an attribute to a URL.
const FORBID_TAGS = [
	"iframe",
	"frame",
	"object",
	"embed",
	"base",
	"meta",
	"link",
	"animate",
	"animatemotion",
	"animatetransform",
	"set",
];
const URL_ATTRIBUTES = new Set(["href", "src", "xlink:href", "action", "formaction"]);
// javascript: runs code, and data: can carry a document that does.
const CODE_SCHEMES = /^(?:javascript|vbscript|data):/;

purifier.addHook("uponSanitizeAttribute", (_node, data) => {
	if (!URL_ATTRIBUTES.has(data.attrName)) return;
	// A browser ignores tabs, newlines and other control characters in a URL's scheme.
	const scheme = data.attrValue.replace(/[\u0000- ]/g, "").toLowerCase();
	if (CODE_SCHEMES.test(scheme)) data.keepAttr = false;
});

export function heldPageHtml(html) {
	return purifier.sanitize(html || "", { FORBID_TAGS, FORBID_ATTR: ["srcdoc"] });
}
