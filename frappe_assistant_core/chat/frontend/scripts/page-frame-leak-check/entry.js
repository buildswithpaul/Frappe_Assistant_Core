// Bundled by vite.config.mjs for run.mjs: the real page-frame host, print and sanitiser code.
import { createPageFrame } from "@/utils/pageFrameHost";
import { printPage } from "@/utils/pagePrint";
import { cleanSnapshot } from "@/utils/pageSnapshotSanitise";

const transport = { get: async () => [], post: async () => null };

// A personal page in its real frame, then FACO's picture of it, drawn inside the frame.
window.captureHostilePage = async (page) => {
	const frame = createPageFrame({ page, kitCss: "", user: "check@example.com", transport, askUser: async () => false });
	frame.element.style.cssText = "width:800px;height:600px;border:0";
	document.body.append(frame.element);
	try {
		const shot = await frame.capture({ scale: 1, quality: 80 });
		const bytes = new Uint8Array(await shot.blob.arrayBuffer());
		const image = btoa(Array.from(bytes, (b) => String.fromCharCode(b)).join(""));
		return { ok: true, bytes: bytes.length, width: shot.width, height: shot.height, text: shot.text, image };
	} catch (error) {
		return { ok: false, error: error.message, detail: error.detail, text: error.text };
	}
};

// Download PDF's frame given markup that was never cleaned: its policy must hold on its own.
window.printRawMarkup = (html) => {
	window.print = () => {};
	printPage({ title: "check", kitCss: "", style: "", html, wide: false, personal: true });
	return true;
};

window.cleanSnapshot = (html) => cleanSnapshot(html);
