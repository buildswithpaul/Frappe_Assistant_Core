/**
 * The widget hardcodes model_id: "auto" (widget.js), so EVERY widget turn is
 * an auto turn — and its model_selected handler was a bare debug log.
 *
 * The widget is plain browser-global JS (not part of the SPA bundle), so the
 * source is loaded and evaluated here against jsdom, exactly as
 * widgetStreamingModelEvent.spec.js does.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as spaCopy from "@/components/chat/routingCopy.js";

const WIDGET_DIR = resolve(process.cwd(), "../../public/chat/widget");

function loadRouting() {
	new Function(readFileSync(`${WIDGET_DIR}/widget_routing.js`, "utf8"))();
	return globalThis.window.FACOWidgetRouting;
}

function loadStreamHandler() {
	globalThis.__ = (s) => s;
	globalThis.FACOLogger = { debug: vi.fn(), warn: vi.fn(), error: vi.fn() };
	globalThis.FACOCore = { format_message: (t) => t, format_time: () => "", get_assistant_avatar: () => "" };
	globalThis.$ = () => ({ length: 0, find: () => ({ length: 0 }) });
	const handlers = {};
	globalThis.frappe = {
		realtime: {
			on: (event, fn) => (handlers[event] = fn),
			task_subscribe: vi.fn(),
			socket: { connected: true, connect: vi.fn() },
		},
		call: vi.fn(),
		utils: { escape_html: (s) => s },
	};
	new Function(readFileSync(`${WIDGET_DIR}/widget_streaming.js`, "utf8"))();
	const streaming = globalThis.window.FACOWidgetStreaming;
	const widget = { session_id: "faco_1", _seenMessageIds: new Set(), messages: [] };
	streaming._bind_socket_listeners(widget);
	return { onStreamEvent: handlers["faco_message_stream"], widget };
}

const RECEIPT = {
	v: 1,
	mode: "auto",
	selected_model: "claude-sonnet-4-6",
	selected_tier: "Standard",
	floor: { tier: "Standard", reasons: ["attachment_document"] },
	ceiling: { tier: "Premium", source: "plan", reasons: [] },
	bound_by: "floor",
	credits: { actual: 12 },
};

describe("the widget catalogue does not drift from the SPA's", () => {
	const MAPS = [
		"TIER_LABELS",
		"FLOOR_REASONS",
		"CEILING_SOURCES",
		"PICK_REASONS",
		"CLASSIFICATION_SOURCES",
		"NOTICES",
		"BAND_LABELS",
		"THINKING_NOT_APPLIED",
		"SUPPRESSED_REASONS",
		"CHIP_EXCEPTIONS",
	];

	for (const name of MAPS) {
		it(`${name} matches routingCopy.js exactly`, () => {
			// Two bundles, one wording. The delivery is duplicated by necessity
			// (the widget cannot import the SPA bundle); the assertion is not.
			expect(loadRouting().CODE_MAPS[name]).toEqual(spaCopy[name]);
		});
	}
});

describe("the widget presenters agree with the SPA's", () => {
	// Comparing two empty strings proves nothing, so each exception is put to
	// both presenters — that is where the two files can actually diverge.
	const EXCEPTIONS = {
		"saver mode": { notices: ["downgraded_for_credits"] },
		"a workspace rule": { preference: { applied: true, scope: "Tenant" } },
		"a FAC Cloud default": { preference: { applied: true, scope: "Application" } },
		"the member's own rule": { preference: { applied: true, scope: "User" } },
		"a mid-answer switch": { fallback_from: "claude-opus-4-6" },
	};

	for (const [what, over] of Object.entries(EXCEPTIONS)) {
		it(`renders the same chip on ${what}`, () => {
			const r = { ...RECEIPT, ...over };
			const label = loadRouting().chipLabel(r);
			expect(label).toBe(spaCopy.routingChipLabel(r));
			expect(label).not.toBe("");
		});
	}

	it("both stay silent on an ordinary turn", () => {
		expect(loadRouting().chipLabel(RECEIPT)).toBe("");
		expect(spaCopy.routingChipLabel(RECEIPT)).toBe("");
	});

	it("renders the same one-line headline", () => {
		expect(loadRouting().headline(RECEIPT, "Sonnet 4.6")).toBe(
			spaCopy.routingHeadline(RECEIPT, "Sonnet 4.6")
		);
	});

	it("agrees on a ceiling-bound turn too", () => {
		const r = { ...RECEIPT, bound_by: "ceiling", ceiling: { tier: "Standard", source: "plan", reasons: [] } };
		expect(loadRouting().headline(r, "S")).toBe(spaCopy.routingHeadline(r, "S"));
	});

	it("agrees on whose rule it was, at every scope", () => {
		// The one place the two bundles could disagree with real consequences:
		// a member on the widget being told their workspace chose a model that
		// FAC Cloud chose.
		for (const scope of ["Application", "Tenant", "User"]) {
			const r = { ...RECEIPT, bound_by: "neither",
				preference: { applied: true, scope, target_tier: "Economy" } };
			expect(loadRouting().headline(r, "S")).toBe(spaCopy.routingHeadline(r, "S"));
		}
		const platform = { ...RECEIPT, bound_by: "neither",
			preference: { applied: true, scope: "Application", target_tier: "Economy" } };
		expect(loadRouting().headline(platform, "S")).toMatch(/FAC Cloud default/);
		expect(loadRouting().headline(platform, "S")).not.toMatch(/workspace/);
	});

	it("agrees when a rule moved the turn", () => {
		const r = { ...RECEIPT, bound_by: "neither",
			preference: { applied: true, scope: "Tenant", target_tier: "Economy" } };
		expect(loadRouting().headline(r, "S")).toBe(spaCopy.routingHeadline(r, "S"));
		expect(loadRouting().headline(r, "S")).toMatch(/workspace rule/);
	});

	it("says nothing without a receipt", () => {
		expect(loadRouting().chipLabel(null)).toBe("");
	});
});

describe("widget streaming — the receipt replaces the debug log", () => {
	let onStreamEvent, widget;

	beforeEach(() => {
		({ onStreamEvent, widget } = loadStreamHandler());
	});

	it("records the receipt on the widget for the turn in flight", () => {
		onStreamEvent({
			session_id: "faco_1",
			event: "model_selected",
			selected: "claude-sonnet-4-6",
			tier: "Standard",
			routing: RECEIPT,
		});
		expect(widget._pending_routing?.selected_model).toBe("claude-sonnet-4-6");
	});

	it("still logs the model the relay names, from the field it sends", () => {
		onStreamEvent({
			session_id: "faco_1",
			event: "model_selected",
			selected: "claude-haiku-4-5",
			tier: "Economy",
		});
		expect(FACOLogger.debug).toHaveBeenCalledWith(
			"Auto mode selected model:",
			"claude-haiku-4-5"
		);
	});
});

describe("both history readers keep the same fields", () => {
	it("_toWidgetMessage exists and is used by both readers", () => {
		const src = readFileSync(`${WIDGET_DIR}/widget.js`, "utf8");
		expect(src).toContain("_toWidgetMessage(");
		// One field list, two readers — the drift that lost `routing` twice.
		const uses = src.match(/this\._toWidgetMessage\(/g) || [];
		expect(uses.length).toBeGreaterThanOrEqual(2);
	});

	it("carries the receipt through, not just role and content", () => {
		const src = readFileSync(`${WIDGET_DIR}/widget.js`, "utf8");
		// The definition, not the first call site.
		const at = src.indexOf("_toWidgetMessage(msg) {");
		expect(at).toBeGreaterThan(-1);
		expect(src.slice(at, at + 400)).toContain("routing");
	});

	it("draws the chip when a LIVE turn lands, not only after a reload", () => {
		// render_routing_chip is called by the history readers; without this
		// the chip appears only when you come back to the conversation.
		const src = readFileSync(`${WIDGET_DIR}/widget_streaming.js`, "utf8");
		const at = src.indexOf("finalize_streaming_message(widget, fullResponse");
		expect(at).toBeGreaterThan(-1);
		const body = src.slice(at, at + 2400);
		expect(body).toContain("render_routing_chip");
		expect(body).toContain("_pending_routing");
	});

	it("the live landing uses the shared field list too", () => {
		// A THIRD place that kept only {role, content} — the same drift.
		const src = readFileSync(`${WIDGET_DIR}/widget_streaming.js`, "utf8");
		const at = src.indexOf("finalize_streaming_message(widget, fullResponse");
		expect(src.slice(at, at + 2400)).toContain("_toWidgetMessage");
	});

	it("clears the pending receipt so it cannot leak into the next turn", () => {
		const src = readFileSync(`${WIDGET_DIR}/widget_streaming.js`, "utf8");
		const at = src.indexOf("finalize_streaming_message(widget, fullResponse");
		expect(src.slice(at, at + 2400)).toContain("widget._pending_routing = null");
	});

	it("the chip is rendered as non-interactive text, never a button", () => {
		// An identical-looking chip opens a panel in the SPA, and users move
		// between the two surfaces.
		const src = readFileSync(`${WIDGET_DIR}/widget.js`, "utf8");
		const at = src.indexOf("render_routing_chip(msg, $message) {");
		expect(at).toBeGreaterThan(-1);
		const body = src.slice(at, at + 1400);
		expect(body).toContain("faco-routing-chip");
		expect(body).not.toContain("<button");
	});

	it("is registered as a widget asset before widget_streaming.js", () => {
		const hooks = readFileSync(
			resolve(process.cwd(), "../../hooks.py"), "utf8");
		const routing = hooks.indexOf("widget/widget_routing.js");
		const streaming = hooks.indexOf("widget/widget_streaming.js");
		expect(routing).toBeGreaterThan(-1);
		expect(routing).toBeLessThan(streaming);
	});
});
