// A held FAC Page's html, as the chat panel draws it before the user clicks Run new version.
// get_page already serves a personal page's html through an allowlist; this is the panel's own
// second line, so nothing in the html runs code before then. Only these tags and attributes stay
// (no inline handlers, srcdoc, script, style or embedding tags), and a dropped tag takes its
// content with it. Forms and buttons stay, because the page's own script may wire them once it runs.
//
// Desk's fac_pages.js keeps the same lists for its own strip; facPagesGate.spec.js fails
// when the two hosts draw a held page differently.
import DOMPurify from "dompurify";

// Its own instance, so the hook below never reaches the chat's markdown sanitising.
const purifier = DOMPurify(window);

export const HELD_TAGS = (
	"a abbr acronym address area article aside audio b big blockquote br button canvas caption center " +
	"cite code col colgroup dd del details dfn div dl dt em fieldset figcaption figure footer form " +
	"h1 h2 h3 h4 h5 h6 header hr i img input ins kbd label legend li main map mark menu meter nav ol " +
	"optgroup option output p pre progress q s samp section select small source span strike strong " +
	"sub summary sup table tbody td textarea tfoot th thead time tr tt u ul var video " +
	"svg g path circle ellipse line polyline polygon rect text tspan defs lineargradient " +
	"radialgradient stop title desc"
).split(" ");

export const HELD_ATTRIBUTES = (
	"class id style title role name type value placeholder for colspan rowspan href src alt width " +
	"height checked disabled selected readonly required multiple min max step rows cols maxlength " +
	"open datetime target rel action method controls poster loop muted preload usemap shape coords " +
	"lang dir align start reversed scope headers label list high low optimum size hidden tabindex " +
	"viewbox xmlns d cx cy r rx ry x y x1 y1 x2 y2 points fill stroke stroke-width " +
	"stroke-linecap stroke-linejoin transform opacity fill-opacity offset stop-color " +
	"text-anchor font-size font-weight dominant-baseline gradientunits"
).split(" ");

const URL_ATTRIBUTES = new Set(["href", "src", "action", "poster"]);
// javascript: runs code, and data: can carry a document that does.
const CODE_SCHEMES = /^(?:javascript|vbscript|data):/;

purifier.addHook("uponSanitizeAttribute", (_node, data) => {
	if (!URL_ATTRIBUTES.has(data.attrName)) return;
	// A browser ignores tabs, newlines and other control characters in a URL's scheme.
	const scheme = data.attrValue.replace(/[\u0000- ]/g, "").toLowerCase();
	if (CODE_SCHEMES.test(scheme)) data.keepAttr = false;
});

export function heldPageHtml(html) {
	return purifier.sanitize(html || "", {
		// An explicit tag list leaves out text unless KEEP_CONTENT is on, so it is named here.
		ALLOWED_TAGS: [...HELD_TAGS, "#text"],
		ALLOWED_ATTR: HELD_ATTRIBUTES,
		KEEP_CONTENT: false,
	});
}
