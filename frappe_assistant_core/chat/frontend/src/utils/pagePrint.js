/**
 * Download PDF for a FAC Page: the browser prints a snapshot of the rendered page from a hidden
 * frame, so the PDF keeps the page's design and its SVG charts without a server round trip.
 */

const FRAME_CLASS = "fac-page-print";

const pad = (n) => String(n).padStart(2, "0");

function today() {
	const now = new Date();
	return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

const escapeHtml = (text) =>
	String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// Style text sits inside <style>; a closing tag in it would end the element early.
const safeStyle = (css) => String(css || "").replace(/<\/style/gi, "<\\/style");

function srcdoc({ name, kitCss, style, html, wide }) {
	const page = `@page { size: A4 ${wide ? "landscape" : "portrait"}; margin: 12mm }`;
	return [
		"<!doctype html>",
		'<html><head><meta charset="utf-8">',
		`<title>${escapeHtml(name)}</title>`,
		`<style>${safeStyle(kitCss)}\n${safeStyle(style)}\n${page}</style>`,
		`</head><body>${html || ""}</body></html>`,
	].join("");
}

/**
 * The markup of a rendered page, for printPage. ECharts draws its live SVG at a fixed pixel size
 * with no viewBox; the copy gets one, so the kit's print rules can scale a chart to the sheet.
 *
 * @param {Element} element the rendered page root
 * @returns {string} its outer html
 */
export function snapshotHtml(element) {
	const copy = element.cloneNode(true);
	copy.querySelectorAll("svg:not([viewBox])").forEach((svg) => {
		const width = parseFloat(svg.getAttribute("width"));
		const height = parseFloat(svg.getAttribute("height"));
		if (width > 0 && height > 0) svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
	});
	return copy.outerHTML;
}

/**
 * Print a page snapshot; the browser's dialog offers Save as PDF under `{title} {YYYY-MM-DD}`.
 *
 * @param {{title: string, kitCss: string, style: string, html: string, wide: boolean}} snapshot
 *   `html` is the rendered page after its script and charts ran; `wide` prints A4 landscape.
 */
export function printPage({ title, kitCss, style, html, wide }) {
	// A frame whose print never reported back must not pile up.
	document.querySelectorAll(`iframe.${FRAME_CLASS}`).forEach((el) => el.remove());

	const name = `${title || ""} ${today()}`.trim();
	const frame = document.createElement("iframe");
	frame.className = FRAME_CLASS;
	// Same origin, so this page can print it; no scripts, so the snapshot's markup stays inert.
	frame.setAttribute("sandbox", "allow-same-origin allow-modals");
	frame.setAttribute("aria-hidden", "true");
	frame.tabIndex = -1;
	// Not display or visibility: some browsers then print a blank page.
	Object.assign(frame.style, { position: "fixed", right: "0", bottom: "0", width: "0", height: "0", border: "0" });
	frame.setAttribute("srcdoc", srcdoc({ name, kitCss, style, html, wide }));

	frame.addEventListener(
		"load",
		() => {
			const win = frame.contentWindow;
			// Browsers differ in which document's title names the PDF, so both carry it while printing.
			const chatTitle = document.title;
			win.document.title = name;
			document.title = name;
			win.addEventListener(
				"afterprint",
				() => {
					if (document.title === name) document.title = chatTitle;
					frame.remove();
				},
				{ once: true },
			);
			win.focus();
			win.print();
		},
		{ once: true },
	);
	document.body.append(frame);
}
