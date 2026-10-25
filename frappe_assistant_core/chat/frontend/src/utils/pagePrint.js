/**
 * Download PDF for a FAC Page: the browser prints a snapshot of the rendered page from a hidden
 * frame, so the PDF keeps the page's design and its SVG charts without a server round trip.
 */

import { FAC_PAGE_DRAFT_CSP } from "@/utils/facPageDraft";
import { today } from "@/utils/pageRuntime";

const FRAME_CLASS = "fac-page-print";

// The chat's own title while a print carries the page's, kept here so that replacing a frame whose
// afterprint never came still gives it back.
let chatTitle = null;
let printTitle = null;

function restoreChatTitle() {
	if (chatTitle !== null && document.title === printTitle) document.title = chatTitle;
	chatTitle = printTitle = null;
}

const escapeHtml = (text) =>
	String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// Style text sits inside <style>; a closing tag in it would end the element early.
const safeStyle = (css) => String(css || "").replace(/<\/style/gi, "<\\/style");

function srcdoc({ name, kitCss, style, html, wide, draft }) {
	const page = `@page { size: A4 ${wide ? "landscape" : "portrait"}; margin: 12mm }`;
	// A draft stays offline when printed, as in its preview; the policy must come before anything
	// it governs.
	const csp = draft ? `<meta http-equiv="Content-Security-Policy" content="${FAC_PAGE_DRAFT_CSP}">` : "";
	return [
		"<!doctype html>",
		`<html><head>${csp}<meta charset="utf-8">`,
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
 * @param {object} snapshot
 * @param {string} snapshot.title the page title
 * @param {string} snapshot.kitCss the mockup kit
 * @param {string} snapshot.style the page's own style
 * @param {string} snapshot.html the rendered page after its script and charts ran
 * @param {boolean} snapshot.wide prints A4 landscape
 * @param {boolean} [snapshot.draft] prints under the draft preview's Content-Security-Policy
 */
export function printPage({ title, kitCss, style, html, wide, draft = false }) {
	// A frame whose print never reported back must not pile up, nor keep the chat's title.
	document.querySelectorAll(`iframe.${FRAME_CLASS}`).forEach((el) => el.remove());
	restoreChatTitle();

	const name = `${title || ""} ${today()}`.trim();
	const frame = document.createElement("iframe");
	frame.className = FRAME_CLASS;
	// Same origin, so this page can print it; no scripts, so the snapshot's markup stays inert.
	frame.setAttribute("sandbox", "allow-same-origin allow-modals");
	frame.setAttribute("aria-hidden", "true");
	frame.tabIndex = -1;
	// Not display or visibility: some browsers then print a blank page.
	Object.assign(frame.style, { position: "fixed", right: "0", bottom: "0", width: "0", height: "0", border: "0" });
	frame.setAttribute("srcdoc", srcdoc({ name, kitCss, style, html, wide, draft }));

	frame.addEventListener(
		"load",
		() => {
			const win = frame.contentWindow;
			// Browsers differ in which document's title names the PDF, so both carry it while printing.
			chatTitle = document.title;
			printTitle = name;
			win.document.title = name;
			document.title = name;
			win.addEventListener(
				"afterprint",
				() => {
					restoreChatTitle();
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
