import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const toolsJs = resolve(process.cwd(), "../../public/chat/widget/widget_browser_tools.js");
const src = () => readFileSync(toolsJs, "utf8");

/**
 * The widget half of the browser-tool budget contract. The server suspends its
 * short delivery deadline only while the widget says a human is deciding, so if
 * these reports stop being emitted — or are emitted in the wrong order —
 * screenshots silently go back to timing out mid-approval.
 */
describe("browser tool progress reports", () => {
	it("reports receipt before doing anything else", () => {
		const handler = src().match(/async _handleToolCall\(data\) \{([\s\S]*?)\n\t\},/);
		expect(handler).not.toBeNull();
		expect(handler[1]).toMatch(/report_progress\(call_id, "received"\)/);
	});

	it("reports awaiting_user BEFORE blocking on the approval card", () => {
		const body = src();
		const awaitingAt = body.indexOf('report_progress(call_id, "awaiting_user")');
		const confirmAt = body.indexOf("await this._requestUserConfirmation(");

		expect(awaitingAt).toBeGreaterThan(-1);
		expect(confirmAt).toBeGreaterThan(-1);
		expect(awaitingAt).toBeLessThan(confirmAt);
	});

	it("reports executing before running the handler", () => {
		const body = src();
		const executingAt = body.indexOf('report_progress(call_id, "executing")');
		const handlerAt = body.indexOf("await handler.call(this.handlers,");

		expect(executingAt).toBeGreaterThan(-1);
		expect(executingAt).toBeLessThan(handlerAt);
	});

	it("does not await progress reports — they must never gate execution", () => {
		const body = src();
		expect(body).not.toMatch(/await this\.report_progress/);
	});

	it("targets the ack endpoint the server actually exposes", () => {
		expect(src()).toMatch(/browser_bridge\.submit_browser_tool_ack/);
	});
});

describe("capture library", () => {
	const hooks = () =>
		readFileSync(resolve(process.cwd(), "../../hooks.py"), "utf8");

	it("loads html2canvas-pro, never the unmaintained 1.4.1", () => {
		// 1.4.1 throws "Error parsing CSS component value, unexpected EOF" on
		// EVERY Frappe Desk page: it reads an empty computed style off its own
		// synthetic <html2canvaspseudoelement> node for ::before/::after, which
		// the Desk uses everywhere. Verified live — the screenshot tool could
		// never succeed with it, regardless of timeouts or capture size.
		const src = hooks();
		expect(src).toMatch(/libs\/html2canvas-pro\.min\.js/);
		expect(src).not.toMatch(/libs\/html2canvas\.min\.js["']/);
	});

	it("version-stamps widget assets so a 12h cached client cannot outlive a deploy", () => {
		const src = hooks();
		expect(src).toMatch(/def _widget_asset\(/);
		expect(src).toMatch(/\?v=\{_WIDGET_ASSET_VERSION\}/);
	});
});

describe("screenshot capture bounds", () => {
	it("caps devicePixelRatio scaling", () => {
		const body = src();
		expect(body).toMatch(/scale: Math\.min\(window\.devicePixelRatio \|\| 1, MAX_SCREENSHOT_SCALE\)/);
		expect(body).toMatch(/const MAX_SCREENSHOT_SCALE = 1\.5/);
	});

	it("overrides html2canvas' 15s-per-image default", () => {
		const body = src();
		expect(body).toMatch(/imageTimeout: SCREENSHOT_IMAGE_TIMEOUT_MS/);
		const value = body.match(/const SCREENSHOT_IMAGE_TIMEOUT_MS = (\d+)/);
		expect(value).not.toBeNull();
		expect(Number(value[1])).toBeLessThan(15000);
	});

	it("caps full-page height", () => {
		expect(src()).toMatch(
			/Math\.min\(document\.body\.scrollHeight, MAX_SCREENSHOT_HEIGHT_PX\)/
		);
	});

	it("does not allow tainting — toBlob throws on a tainted canvas", () => {
		expect(src()).toMatch(/allowTaint: false/);
		expect(src()).not.toMatch(/allowTaint: true/);
	});

	it("handles the null blob an oversized canvas produces", () => {
		// Without this, `new File([null])` uploads the 4-byte string "null" and
		// the upload endpoint rejects it as a magic-byte mismatch.
		const body = src();
		const blobAt = body.indexOf("canvas.toBlob(resolve");
		const guardAt = body.indexOf("if (!blob)");

		expect(guardAt).toBeGreaterThan(blobAt);
		expect(body.slice(guardAt, guardAt + 400)).toMatch(/Screenshot too large/);
	});
});
