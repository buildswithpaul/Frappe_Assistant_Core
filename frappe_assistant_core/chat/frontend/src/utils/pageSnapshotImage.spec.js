import { afterEach, describe, expect, it, vi } from "vitest";

// jsdom cannot run html2canvas (its cloning frame never loads), so the stand-in records what it is
// given; the real html2canvas-pro is run against the same code in Chrome (see task-8-report.md).
const h2c = vi.hoisted(() => ({ calls: [] }));
vi.mock("html2canvas-pro", () => ({
	default: async (el, options) => {
		h2c.calls.push({ el, options, frame: document.querySelector("iframe") });
		return { width: 640, height: 900, toBlob: (cb, type) => cb(new Blob(["jpeg"], { type })) };
	},
}));

import { canvasOptions, snapshotToJpeg } from "./pageSnapshotImage";

const ORIGIN = window.location.origin;

afterEach(() => {
	h2c.calls = [];
});

describe("canvasOptions", () => {
	it("fetches nothing cross-origin, through no proxy, and counts only site files as same-origin", () => {
		const options = canvasOptions({ origin: ORIGIN });
		expect(options.useCORS).toBe(false);
		expect(options.allowTaint).toBe(false);
		expect(options.proxy).toBeUndefined();
		expect(options.customIsSameOrigin(`${ORIGIN}/files/a.png`)).toBe(true);
		expect(options.customIsSameOrigin("https://evil.example/a.png")).toBe(false);
		expect(options.customIsSameOrigin(`${ORIGIN}/api/method/logout`)).toBe(false);
	});

	it("skips anything that embeds or loads", () => {
		const { ignoreElements } = canvasOptions();
		for (const tag of ["iframe", "object", "embed", "link", "script", "video", "audio"]) {
			expect(ignoreElements(document.createElement(tag)), tag).toBe(true);
		}
		expect(ignoreElements(document.createElement("div"))).toBe(false);
	});
});

describe("snapshotToJpeg", () => {
	it("draws only cleaned markup, in a same-origin frame that runs no script", async () => {
		const html =
			'<div class="fac-page-root"><p>₹70,29,354</p><img src="https://evil.example/c?d=1">' +
			'<div style="background:url(https://evil.example/bg)"></div></div>';
		const shot = await snapshotToJpeg({ html, kitCss: ".kit{}", style: "p{color:teal}", width: 640, quality: 70 });
		const { frame, options } = h2c.calls[0];
		expect(frame.getAttribute("sandbox")).toBe("allow-same-origin");
		const doc = new DOMParser().parseFromString(frame.getAttribute("srcdoc"), "text/html");
		const policy = doc.head.firstElementChild;
		expect(policy.getAttribute("http-equiv")).toBe("Content-Security-Policy");
		expect(policy.getAttribute("content")).toContain("default-src 'none'");
		expect(doc.body.textContent).toContain("₹70,29,354");
		expect(doc.body.innerHTML).not.toContain("evil.example");
		expect(options.useCORS).toBe(false);
		expect(frame.style.width).toBe("640px");
		expect(shot).toMatchObject({ width: 640, height: 900 });
		expect(shot.blob.type).toBe("image/jpeg");
		// The frame is gone once the picture is taken.
		expect(document.querySelector("iframe")).toBeNull();
	});
});
