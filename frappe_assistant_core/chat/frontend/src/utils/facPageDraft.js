// Draft preview for a FAC Page in the chat panel. The fac-pages Desk page keeps its own copy in
// assistant_core/page/fac_pages/fac_page_draft.js, because render_include inlines a plain script
// and cannot load a module; utils/__tests__/facPageDraftCases.js tests both copies against the
// same cases.
//
// A draft is dormant, so the browser itself keeps it from running code or reaching the network:
// it renders in an iframe with an empty sandbox (no scripts, forms, popups or top navigation) and
// a Content-Security-Policy that allows only inline styles and data: images.

const FAC_PAGE_DRAFT_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:";

export function fac_page_draft_srcdoc({ html, style, kit_css } = {}) {
	// A style that closes its own tag would otherwise end the style element early.
	const css = `${kit_css || ""}\n${style || ""}`.replace(/<\/style/gi, "<\\/style");
	return (
		"<!doctype html><html><head>" +
		`<meta http-equiv="Content-Security-Policy" content="${FAC_PAGE_DRAFT_CSP}">` +
		'<meta charset="utf-8">' +
		`<style>${css}</style>` +
		`</head><body><div class="fac-page-root">${html || ""}</div></body></html>`
	);
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
