// Draft preview for the fac-pages Desk page. Keep this first line a comment: fac_pages.js inlines
// the file through Frappe's render_include from a line that starts with "//".
//
// A draft is dormant, so the browser itself keeps it from running code or reaching the network:
// it renders in an iframe with an empty sandbox (no scripts, forms, popups or top navigation) and
// a Content-Security-Policy that allows only inline styles and data: images. The chat panel has an
// ES-module copy in chat/frontend/src/utils/facPageDraft.js; both are tested against the cases in
// chat/frontend/src/utils/facPageDraftCases.js, run by
// chat/frontend/src/widget/desk/facPageDraft.spec.js.

const FAC_PAGE_DRAFT_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:";

// eslint-disable-next-line no-unused-vars
function fac_page_draft_srcdoc({ html, style, kit_css } = {}) {
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

// eslint-disable-next-line no-unused-vars
function fac_page_draft_frame(parts) {
	const frame = document.createElement("iframe");
	frame.setAttribute("sandbox", "");
	frame.className = "fac-page-draft-frame";
	// A frame without scripts cannot report its height, so it fills the page area instead.
	frame.style.cssText = "display:block;width:100%;min-height:calc(100vh - 160px);border:0;";
	frame.srcdoc = fac_page_draft_srcdoc(parts);
	return frame;
}
