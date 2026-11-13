// Draft preview for a FAC Page in the chat panel. The fac-pages Desk page keeps its own copy in
// assistant_core/page/fac_pages/fac_page_draft.js, because render_include inlines a plain script
// and cannot load a module; utils/__tests__/facPageDraftCases.js tests both copies against the
// same cases.
//
// A draft is dormant, so the browser itself keeps it from running code or reaching the network:
// it renders in an iframe with an empty sandbox (no scripts, forms, popups or top navigation) and
// a Content-Security-Policy that allows only inline styles and data: images.

export const FAC_PAGE_DRAFT_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:";

export function fac_page_draft_srcdoc({ html, style, kit_css, theme } = {}) {
	// A style that closes its own tag would otherwise end the style element early.
	const css = `${kit_css || ""}\n${style || ""}`.replace(/<\/style/gi, "<\\/style");
	return (
		`<!doctype html><html data-theme="${theme === "dark" ? "dark" : "light"}"><head>` +
		`<meta http-equiv="Content-Security-Policy" content="${FAC_PAGE_DRAFT_CSP}">` +
		'<meta charset="utf-8">' +
		`<style>${css}</style>` +
		`</head><body><div class="fac-page-root">${html || ""}</div></body></html>`
	);
}

// A page follows Desk's dark theme only when it colours with the kit's tokens. One that names its
// own colours, in its style or an inline style, stays light: a fixed white card would otherwise
// hold the dark theme's light text.
const FAC_PAGE_OWN_COLOUR =
	/#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\s*\(|\b(?:white|black|red|green|blue|gray|grey|silver|orange|yellow|purple|navy|teal|maroon)\b/i;

function fac_page_sets_own_colours({ html, style } = {}) {
	// Only declaration values: an id selector such as #add-row is not a colour.
	const values = [...String(style || "").matchAll(/:\s*([^;{}]+)/g)].map((m) => m[1]);
	for (const m of String(html || "").matchAll(/\b(?:style|color|bgcolor)\s*=\s*(?:"([^"]*)"|'([^']*)')/gi)) {
		values.push(m[1] ?? m[2]);
	}
	return values.some((value) => FAC_PAGE_OWN_COLOUR.test(value));
}

export function fac_page_shown_theme(page, desk_theme) {
	return desk_theme === "dark" && !fac_page_sets_own_colours(page) ? "dark" : "light";
}

export function fac_page_draft_frame(parts) {
	const frame = document.createElement("iframe");
	frame.setAttribute("sandbox", "");
	frame.className = "fac-page-draft-frame";
	// A frame without scripts cannot report its height, so it fills the page area instead.
	frame.style.cssText = "display:block;width:100%;min-height:calc(100vh - 160px);border:0;";
	frame.srcdoc = fac_page_draft_srcdoc(parts);
	return frame;
}
