/**
 * FACO's picture of a personal page. The page's frame has an opaque origin, which html2canvas
 * cannot clone into, so the frame sends its rendered markup and the picture is drawn from that
 * here: in a hidden frame that is this site's origin, so html2canvas can read it, but runs no
 * script and, under personalPrintCsp, loads nothing from another server.
 */
import { snapshotSrcdoc } from "@/utils/pagePrint";

const loadHtml2canvas = () => import("html2canvas-pro").then((m) => m.default || m);

const IMAGE_TIMEOUT_MS = 3000;

/**
 * @param {object} snapshot
 * @param {string} snapshot.html the page's rendered markup, from its frame
 * @param {string} snapshot.kitCss the mockup kit
 * @param {string} snapshot.style the page's own style
 * @param {number} snapshot.width the width the page is drawn at, as in the panel
 * @param {number} [snapshot.scale]
 * @param {number} [snapshot.quality] JPEG quality, 1-100
 * @returns {Promise<{blob: Blob|null, width: number, height: number}>}
 */
export async function snapshotToJpeg({ html, kitCss, style, width, scale = 1, quality = 80 }) {
	const frame = document.createElement("iframe");
	// Same origin, so html2canvas can read it from here; no scripts, so the markup stays inert.
	frame.setAttribute("sandbox", "allow-same-origin");
	frame.setAttribute("aria-hidden", "true");
	frame.tabIndex = -1;
	// Laid out at the panel's width, out of sight; not display:none, which lays nothing out.
	Object.assign(frame.style, {
		position: "fixed",
		left: "-10000px",
		top: "0",
		width: `${Math.max(320, Math.round(width) || 0)}px`,
		height: "800px",
		border: "0",
	});
	frame.setAttribute("srcdoc", snapshotSrcdoc({ name: "", kitCss, style, html, wide: false, personal: true }));
	const loaded = new Promise((resolve) => frame.addEventListener("load", resolve, { once: true }));
	document.body.append(frame);
	try {
		await loaded;
		const doc = frame.contentDocument;
		const target = doc.querySelector(".fac-page-root") || doc.body;
		const html2canvas = await loadHtml2canvas();
		const canvas = await html2canvas(target, {
			useCORS: true,
			allowTaint: false,
			backgroundColor: "#ffffff",
			scale,
			imageTimeout: IMAGE_TIMEOUT_MS,
			logging: false,
		});
		const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality / 100));
		return { blob, width: canvas.width, height: canvas.height };
	} finally {
		frame.remove();
	}
}
