import { afterEach, describe, expect, it, vi } from "vitest";

const h2c = vi.hoisted(() => ({ calls: [] }));
vi.mock("html2canvas-pro", () => ({
	default: async (el, options) => {
		h2c.calls.push({ el, options, frame: document.querySelector("iframe") });
		return { width: 640, height: 900, toBlob: (cb, type) => cb(new Blob(["jpeg"], { type })) };
	},
}));

import { snapshotToJpeg } from "./pageSnapshotImage";

afterEach(() => {
	h2c.calls = [];
});

describe("snapshotToJpeg", () => {
	it("draws the markup in a same-origin frame that runs no script and reaches no other server", async () => {
		const shot = await snapshotToJpeg({
			html: '<div class="fac-page-root"><p>₹70,29,354</p></div>',
			kitCss: ".kit{}",
			style: "p{color:teal}",
			width: 640,
			quality: 70,
		});
		const { frame } = h2c.calls[0];
		expect(frame.getAttribute("sandbox")).toBe("allow-same-origin");
		const doc = new DOMParser().parseFromString(frame.getAttribute("srcdoc"), "text/html");
		const policy = doc.head.firstElementChild;
		expect(policy.getAttribute("http-equiv")).toBe("Content-Security-Policy");
		expect(policy.getAttribute("content")).toContain("default-src 'none'");
		expect(doc.body.textContent).toContain("₹70,29,354");
		expect(frame.style.width).toBe("640px");
		expect(shot).toMatchObject({ width: 640, height: 900 });
		expect(shot.blob.type).toBe("image/jpeg");
		// The frame is gone once the picture is taken.
		expect(document.querySelector("iframe")).toBeNull();
	});
});
