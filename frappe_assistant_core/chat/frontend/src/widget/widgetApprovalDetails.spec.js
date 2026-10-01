/**
 * Approval-card detail rows in the Desk widget's streaming module.
 *
 * The widget is plain browser-global JS (not part of the SPA bundle), so the
 * source is loaded and evaluated here against jsdom + stubbed Frappe globals.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// vitest runs from the frontend package root (its config lives there).
const WIDGET_SRC = resolve(process.cwd(), "../../public/chat/widget/widget_streaming.js");

function loadStreamingModule() {
	globalThis.__ = (s) => s;
	globalThis.FACOLogger = { debug: vi.fn(), warn: vi.fn(), error: vi.fn() };
	globalThis.FACOCore = { format_message: (t) => t, format_time: () => "", get_assistant_avatar: () => "" };
	globalThis.$ = () => ({ length: 0, find: () => ({ length: 0 }) });
	globalThis.frappe = {
		realtime: { on: vi.fn(), socket: { connected: true, connect: vi.fn() } },
		call: vi.fn(),
		utils: { escape_html: (s) => s },
	};
	new Function(readFileSync(WIDGET_SRC, "utf8"))();
	return globalThis.window.FACOWidgetStreaming;
}

const DOC = { doctype: "Sales Invoice", name: "ACC-SINV-2026-00007" };

describe("widget approval card — document_action reason row", () => {
	let S;
	const keys = (toolName, input) => S._approval_detail_entries(toolName, input).map(([k]) => k);

	beforeEach(() => {
		S = loadStreamingModule();
	});

	it("hides reason on submit, default submit and amend", () => {
		expect(keys("document_action", { ...DOC, action: "submit", reason: "" })).not.toContain("reason");
		expect(keys("document_action", { ...DOC, reason: "" })).not.toContain("reason");
		expect(keys("document_action", { ...DOC, action: "amend", reason: "leftover" })).not.toContain("reason");
	});

	it("shows reason on cancel, and hides it when blank", () => {
		expect(keys("document_action", { ...DOC, action: "cancel", reason: "Billed twice" })).toContain("reason");
		expect(keys("document_action", { ...DOC, action: "cancel", reason: "  " })).not.toContain("reason");
	});

	it("leaves other tools' rows alone", () => {
		expect(keys("update_document", { ...DOC, reason: "" })).toContain("reason");
	});
});
