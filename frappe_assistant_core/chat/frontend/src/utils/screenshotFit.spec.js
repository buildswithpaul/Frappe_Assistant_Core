import { describe, expect, it } from "vitest";

import {
	SCREENSHOT_MAX_EDGE_PX,
	SCREENSHOT_MAX_PIXELS,
	SCREENSHOT_MIN_SCALE,
	describeScreenshotFit,
	fitScreenshot,
} from "./screenshotFit";

// Anthropic refuses an image over 8000 px a side (Redmine #34698).
const PROVIDER_MAX_EDGE = 8000;
const drawn = (page, fit) => ({ width: Math.ceil(page.width * fit.scale), height: Math.ceil(fit.height * fit.scale) });

describe("fitScreenshot", () => {
	it("leaves an ordinary page at the scale it asked for", () => {
		expect(fitScreenshot({ width: 1280, height: 2000, scale: 1.5 })).toEqual({ scale: 1.5, height: 2000 });
	});

	it("scales a 10,000 px tall page to fit, keeping all of it", () => {
		const page = { width: 1280, height: 10000 };
		const fit = fitScreenshot({ ...page, scale: 1.5 });
		const picture = drawn(page, fit);

		expect(fit.height).toBe(10000);
		expect(fit.scale).toBeGreaterThanOrEqual(SCREENSHOT_MIN_SCALE);
		expect(Math.max(picture.width, picture.height)).toBeLessThanOrEqual(PROVIDER_MAX_EDGE);
		expect(picture.width * picture.height).toBeLessThanOrEqual(SCREENSHOT_MAX_PIXELS * 1.01);
	});

	it("keeps the top of a page too tall to scale readably, at the smallest readable scale", () => {
		const page = { width: 1280, height: 30000 };
		const fit = fitScreenshot({ ...page, scale: 1.5 });
		const picture = drawn(page, fit);

		expect(fit.scale).toBe(SCREENSHOT_MIN_SCALE);
		expect(fit.height).toBe(SCREENSHOT_MAX_EDGE_PX / SCREENSHOT_MIN_SCALE);
		expect(Math.max(picture.width, picture.height)).toBeLessThanOrEqual(PROVIDER_MAX_EDGE);
	});

	it("keeps a wide page under the pixel budget", () => {
		const page = { width: 2560, height: 9000 };
		const fit = fitScreenshot({ ...page, scale: 1.5 });
		const picture = drawn(page, fit);
		expect(picture.width * picture.height).toBeLessThanOrEqual(SCREENSHOT_MAX_PIXELS * 1.01);
		expect(Math.max(picture.width, picture.height)).toBeLessThanOrEqual(PROVIDER_MAX_EDGE);
	});
});

describe("describeScreenshotFit", () => {
	it("says nothing about a picture of the whole page at the usual scale", () => {
		expect(describeScreenshotFit({ pageWidth: 1280, pageHeight: 2000, width: 1920, height: 3000, scale: 1.5 })).toEqual({});
	});

	it("says a picture was scaled, and the page's own size", () => {
		const result = describeScreenshotFit({ pageWidth: 1280, pageHeight: 10000, width: 983, height: 7680, scale: 1.5 });
		expect(result).toMatchObject({ scaled: true, cropped: false, original_size: { width: 1280, height: 10000 } });
		expect(result.size_note).toMatch(/shows all of it, scaled to 77%/);
	});

	it("says how much of a cut page the picture keeps", () => {
		const result = describeScreenshotFit({ pageWidth: 1280, pageHeight: 30000, width: 640, height: 7680, scale: 1.5 });
		expect(result).toMatchObject({ scaled: true, cropped: true, kept_height: 15360 });
		expect(result.size_note).toMatch(/only the top 15360 px \(51% of the page\)/);
		expect(result.size_note).toMatch(/rest of the page is not in the picture/);
	});

	it("says nothing when the page's size is unknown", () => {
		expect(describeScreenshotFit({ width: 640, height: 480, scale: 1 })).toEqual({});
	});
});
