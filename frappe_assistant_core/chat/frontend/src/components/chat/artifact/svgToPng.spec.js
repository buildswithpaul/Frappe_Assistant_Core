import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { svgToPng } from "./svgToPng";

describe("svgToPng", () => {
	let origImage, fillRectCalls, drawnAt;

	beforeEach(() => {
		fillRectCalls = [];
		drawnAt = null;

		// jsdom does not implement URL.createObjectURL/revokeObjectURL.
		vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL() {} });

		// Mock Image so onload fires synchronously with known dimensions.
		origImage = global.Image;
		global.Image = class {
			set src(_v) {
				// fire onload on next microtask
				Promise.resolve().then(() => this.onload && this.onload());
			}
			get width() {
				return 200;
			}
			get height() {
				return 100;
			}
		};

		// Mock canvas + 2D context.
		vi.spyOn(document, "createElement").mockImplementation((tag) => {
			if (tag !== "canvas") return document.createElementNS("x", tag);
			return {
				width: 0,
				height: 0,
				getContext: () => ({
					fillStyle: "",
					fillRect: (...a) => fillRectCalls.push(a),
					drawImage: (_img, x, y, w, h) => (drawnAt = { x, y, w, h }),
				}),
				toDataURL: (type) => `data:${type};base64,STUB`,
			};
		});
	});

	afterEach(() => {
		global.Image = origImage;
		vi.restoreAllMocks();
		vi.unstubAllGlobals();
	});

	function makeSvg() {
		const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
		svg.setAttribute("width", "200");
		svg.setAttribute("height", "100");
		return svg;
	}

	it("returns a png dataURL", async () => {
		const url = await svgToPng(makeSvg(), 2);
		expect(url).toBe("data:image/png;base64,STUB");
	});

	it("scales the canvas to 2x the intrinsic size", async () => {
		await svgToPng(makeSvg(), 2);
		// drawImage called at full canvas size (200*2 x 100*2)
		expect(drawnAt).toEqual({ x: 0, y: 0, w: 400, h: 200 });
	});

	it("fills a white background before drawing", async () => {
		await svgToPng(makeSvg(), 2);
		expect(fillRectCalls.length).toBe(1);
		expect(fillRectCalls[0]).toEqual([0, 0, 400, 200]);
	});

	it("sizes the canvas from the viewBox when width is a percentage", async () => {
		const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
		svg.setAttribute("width", "100%");
		svg.setAttribute("viewBox", "0 0 300 150");
		await svgToPng(svg, 2);
		// viewBox 300x150 at 2x → 600x300
		expect(drawnAt).toEqual({ x: 0, y: 0, w: 600, h: 300 });
	});

	it("prefers viewBox over a numeric width attr", async () => {
		const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
		svg.setAttribute("width", "200");
		svg.setAttribute("height", "100");
		svg.setAttribute("viewBox", "0 0 400 200");
		await svgToPng(svg, 2);
		// viewBox wins: 400x200 at 2x → 800x400
		expect(drawnAt).toEqual({ x: 0, y: 0, w: 800, h: 400 });
	});

	it("rejects when given no svg", async () => {
		await expect(svgToPng(null, 2)).rejects.toThrow();
	});

	it("rejects and revokes the object URL when the image fails to load", async () => {
		const revoke = vi.fn();
		vi.stubGlobal("URL", {
			createObjectURL: () => "blob:err",
			revokeObjectURL: revoke,
		});
		global.Image = class {
			set src(_v) {
				Promise.resolve().then(() => this.onerror && this.onerror(new Event("error")));
			}
		};
		await expect(svgToPng(makeSvg(), 2)).rejects.toThrow("image load failed");
		expect(revoke).toHaveBeenCalledWith("blob:err");
	});
});
