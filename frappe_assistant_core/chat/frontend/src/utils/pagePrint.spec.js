import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FAC_PAGE_DRAFT_CSP } from "./facPageDraft";
import { printPage, snapshotHtml } from "./pagePrint";

const snapshot = {
	title: "Sales",
	kitCss: ".mk-card { border: 1px solid; }",
	style: ".mk-card { color: teal; }",
	html: '<div class="fac-page-root"><div class="mk-card"><svg width="400" height="200"><rect/></svg></div></div>',
	wide: false,
};

const frame = () => document.querySelector("iframe.fac-page-print");

// jsdom ignores srcdoc (it loads about:blank) and cannot focus or print a window; a browser
// parses the snapshot and opens its print dialog here.
const contentWindow = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, "contentWindow");
function stubPrinting() {
	Object.defineProperty(HTMLIFrameElement.prototype, "contentWindow", {
		configurable: true,
		get() {
			const win = contentWindow.get.call(this);
			if (win && !vi.isMockFunction(win.print)) Object.assign(win, { print: vi.fn(), focus: vi.fn() });
			return win;
		},
	});
}

async function loadFrame() {
	await new Promise((resolve) => frame().addEventListener("load", resolve, { once: true }));
	return frame().contentWindow;
}

beforeEach(() => {
	stubPrinting();
	vi.useFakeTimers({ toFake: ["Date"] });
	vi.setSystemTime(new Date(2026, 9, 5, 10, 0));
	document.title = "FAC Chat";
});

afterEach(() => {
	Object.defineProperty(HTMLIFrameElement.prototype, "contentWindow", contentWindow);
	vi.useRealTimers();
	frame()?.remove();
});

describe("printPage", () => {
	it("prints the snapshot with the kit, the page style and an A4 portrait page", () => {
		printPage(snapshot);
		const srcdoc = frame().getAttribute("srcdoc");
		expect(srcdoc).toContain(snapshot.kitCss);
		expect(srcdoc).toContain(snapshot.style);
		expect(srcdoc).toContain("@page { size: A4 portrait; margin: 12mm }");
		expect(srcdoc).toContain('<svg width="400" height="200"><rect/></svg>');
		expect(srcdoc.indexOf(snapshot.kitCss)).toBeLessThan(srcdoc.indexOf(snapshot.style));
	});

	it("prints a draft under the draft's CSP, as the first thing in its head", () => {
		printPage({ ...snapshot, draft: true });
		const srcdoc = frame().getAttribute("srcdoc");
		expect(srcdoc).toContain(
			`<head><meta http-equiv="Content-Security-Policy" content="${FAC_PAGE_DRAFT_CSP}">`,
		);
	});

	it("prints a personal page's markup under a policy that reaches only the site's public paths", () => {
		// The markup came out of the frame that runs FACO's code; printed here, it must load nothing else.
		printPage({ ...snapshot, html: '<img src="https://evil.example/x.png">', personal: true });
		const meta = new DOMParser()
			.parseFromString(frame().getAttribute("srcdoc"), "text/html")
			.head.firstElementChild;
		expect(meta.getAttribute("http-equiv")).toBe("Content-Security-Policy");
		const csp = meta.getAttribute("content");
		expect(csp).toContain("default-src 'none'");
		expect(csp).toContain(`img-src ${window.location.origin}/files/ ${window.location.origin}/assets/ data: blob:`);
		expect(csp).not.toContain("evil.example");
		expect(csp).toContain("base-uri 'none'");
		expect(csp).toContain("form-action 'none'");
		const doc = new DOMParser().parseFromString(frame().getAttribute("srcdoc"), "text/html");
		expect(doc.querySelector('meta[http-equiv="x-dns-prefetch-control"]').getAttribute("content")).toBe("off");
	});

	it("prints a published page without the draft CSP", () => {
		printPage(snapshot);
		expect(frame().getAttribute("srcdoc")).not.toContain("Content-Security-Policy");
	});

	it("gives the chat its title back when a frame whose print never reported back is replaced", async () => {
		printPage(snapshot);
		await loadFrame();
		expect(document.title).toBe("Sales 2026-10-05");
		printPage({ ...snapshot, title: "Costs" });
		expect(document.title).toBe("FAC Chat");
		const win = await loadFrame();
		expect(document.title).toBe("Costs 2026-10-05");
		win.dispatchEvent(new Event("afterprint"));
		expect(document.title).toBe("FAC Chat");
	});

	it("prints landscape when the page is wide", () => {
		printPage({ ...snapshot, wide: true });
		expect(frame().getAttribute("srcdoc")).toContain("@page { size: A4 landscape; margin: 12mm }");
	});

	it("names the print after the page and today's date", async () => {
		printPage(snapshot);
		expect(frame().getAttribute("srcdoc")).toContain("<title>Sales 2026-10-05</title>");
		const win = await loadFrame();
		expect(win.document.title).toBe("Sales 2026-10-05");
		expect(win.print).toHaveBeenCalledOnce();
	});

	it("escapes the title", () => {
		printPage({ ...snapshot, title: "<b>Q3</b> & more" });
		expect(frame().getAttribute("srcdoc")).toContain("<title>&lt;b&gt;Q3&lt;/b&gt; &amp; more 2026-10-05</title>");
	});

	it("names the print in the chat's title too, and puts it back after printing", async () => {
		printPage(snapshot);
		const win = await loadFrame();
		expect(document.title).toBe("Sales 2026-10-05");
		win.dispatchEvent(new Event("afterprint"));
		expect(document.title).toBe("FAC Chat");
	});

	it("removes the frame after printing", async () => {
		printPage(snapshot);
		const win = await loadFrame();
		win.dispatchEvent(new Event("afterprint"));
		expect(frame()).toBeNull();
	});

	it("keeps at most one print frame", () => {
		printPage(snapshot);
		printPage(snapshot);
		expect(document.querySelectorAll("iframe.fac-page-print")).toHaveLength(1);
	});

	it("runs nothing in the snapshot: scripts stay off and only the print dialog is allowed", () => {
		printPage(snapshot);
		expect(frame().getAttribute("sandbox")).toBe("allow-same-origin allow-modals");
	});

	it("keeps a page style from closing the style element", () => {
		printPage({ ...snapshot, style: "</style><script>alert(1)</script>" });
		expect(frame().getAttribute("srcdoc")).not.toContain("</style><script>");
	});

	it("keeps the frame out of sight", () => {
		printPage(snapshot);
		expect(frame().getAttribute("aria-hidden")).toBe("true");
		// Not display or visibility: some browsers then print a blank page.
		expect(frame().style.width).toBe("0px");
		expect(frame().style.height).toBe("0px");
	});
});

describe("snapshotHtml", () => {
	it("copies the page and gives a fixed-size svg a viewBox, so print can scale it", () => {
		const root = document.createElement("div");
		root.className = "fac-page-root";
		root.innerHTML = '<svg width="960" height="320"><rect/></svg><svg viewBox="0 0 1 1" width="5" height="5"></svg>';
		const html = snapshotHtml(root);
		expect(html).toContain('<svg width="960" height="320" viewBox="0 0 960 320">');
		expect(html).toContain('<svg viewBox="0 0 1 1" width="5" height="5">');
		expect(root.querySelector("svg").hasAttribute("viewBox")).toBe(false);
	});
});
