/**
 * The Desk widget listened for "model_fallback" and read `selected_model`;
 * the relay emits "model_selected" and carries the id in `selected`, so the
 * widget's auto-mode reporting had been dead on both counts.
 *
 * The widget is plain browser-global JS (not part of the SPA bundle), so the
 * source is loaded and evaluated here against jsdom + stubbed Frappe globals.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// vitest runs from the frontend package root (its config lives there).
const WIDGET_SRC = resolve(process.cwd(), "../../public/chat/widget/widget_streaming.js");

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
	new Function(readFileSync(WIDGET_SRC, "utf8"))();

	const streaming = globalThis.window.FACOWidgetStreaming;
	streaming._bind_socket_listeners({ session_id: "faco_1", _seenMessageIds: new Set() });
	return handlers["faco_message_stream"];
}

describe("widget streaming — auto-mode model reporting", () => {
	let onStreamEvent;

	beforeEach(() => {
		onStreamEvent = loadStreamHandler();
	});

	it("reports the model the relay actually names, from the field it actually sends", () => {
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
