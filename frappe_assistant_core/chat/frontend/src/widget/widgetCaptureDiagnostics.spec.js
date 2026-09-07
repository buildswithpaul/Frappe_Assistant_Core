import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC = resolve(process.cwd(), "../../public/chat/widget/widget_browser_tools.js");
const src = () => readFileSync(SRC, "utf8");

/**
 * Source-text assertions, matching the existing widgetBrowserTools.spec.js
 * convention: this file is a global script wired into a live Desk page, so the
 * contract worth pinning is that the wiring exists and is gated.
 */
describe("capture_diagnostics handler", () => {
	it("is registered as a handler", () => {
		expect(src()).toMatch(/async capture_diagnostics\(params\)/);
	});

	// A commented-out entry (e.g. `// "capture_diagnostics",`) still contains the
	// substring, so line comments are stripped before asserting on what's active.
	const withoutLineComments = (text) => text.replace(/\/\/[^\n]*/g, "");

	it("requires user confirmation like the other sensitive reads", () => {
		const set = src().match(/TOOLS_REQUIRING_CONFIRMATION = new Set\(\[([\s\S]*?)\]\)/);
		expect(set).not.toBeNull();
		expect(withoutLineComments(set[1])).toContain("capture_diagnostics");
	});

	it("has approval-card copy so the user is told what is collected", () => {
		const copy = src().match(/TOOL_CONFIRMATION_COPY = \{([\s\S]*?)\n\};/);
		expect(copy).not.toBeNull();
		expect(withoutLineComments(copy[1])).toContain("capture_diagnostics");
	});

	it("calls the screenshot handler directly so only ONE approval card is raised", () => {
		const handler = src().match(/async capture_diagnostics\(params\) \{([\s\S]*?)\n\t\t\},/);
		// Positive: the actual direct call, not just the bare tool name.
		expect(handler[1]).toMatch(/FACOBrowserTools\.handlers\.take_screenshot\(/);
		// Negative: never re-enters the routed tool-call path, which would raise
		// a second confirmation card — the exact regression this design prevents.
		expect(handler[1]).not.toMatch(/_handleToolCall/);
	});

	it("degrades to console and network when the screenshot fails", () => {
		const handler = src().match(/async capture_diagnostics\(params\) \{([\s\S]*?)\n\t\t\},/);
		expect(handler[1]).toMatch(/screenshot_error/);
	});

	it("reports diagnostics_enabled so the model knows an empty buffer is a setting", () => {
		const handler = src().match(/async capture_diagnostics\(params\) \{([\s\S]*?)\n\t\t\},/);
		expect(handler[1]).toMatch(/diagnostics_enabled/);
	});
});
