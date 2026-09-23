/**
 * Reconnect-recovery tests for the Desk widget's streaming module.
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

function makeWidget(overrides = {}) {
	return Object.assign(
		{
			session_id: "faco_1",
			current_message_id: null,
			_isStreaming: true,
			_seenMessageIds: new Set(),
			messages: [],
			$widget: { find: () => ({ length: 0, remove() {}, prop() {}, hide() {}, show() {} }) },
			add_message_to_ui: vi.fn(),
		},
		overrides
	);
}

describe("widget streaming — row finalization", () => {
	let S;
	beforeEach(() => {
		S = loadStreamingModule();
	});

	it("treats an assistant row with content as finished", () => {
		expect(S._is_finalized_row({ role: "assistant", content: "done" })).toBe(true);
	});

	it("treats the stream_start shell row as unfinished", () => {
		expect(S._is_finalized_row({ role: "assistant", content: "", blocks: "[]" })).toBe(false);
	});

	it("treats a terminal flag as finished even without content", () => {
		expect(S._is_finalized_row({ role: "assistant", content: "", errored: 1 })).toBe(true);
		expect(S._is_finalized_row({ role: "assistant", content: "", aborted: 1 })).toBe(true);
	});

	it("parses the blocks JSON string the server sends", () => {
		const row = { role: "assistant", content: "", blocks: '[{"type":"text"}]' };
		expect(S._is_finalized_row(row)).toBe(true);
		expect(S._is_finalized_row({ role: "assistant", content: "", blocks: "not json" })).toBe(false);
	});

	it("never treats a user row as an adoptable answer", () => {
		expect(S._is_finalized_row({ role: "user", content: "hi" })).toBe(false);
	});
});

describe("widget streaming — recovery row selection", () => {
	let S;
	beforeEach(() => {
		S = loadStreamingModule();
	});

	it("adopts the row matching the turn's message_id", () => {
		const rows = [
			{ role: "user", content: "hi", message_id: null },
			{ role: "assistant", content: "the answer", message_id: "m1" },
		];
		expect(S._pick_recovery_row(rows, "m1", new Set())).toBe(rows[1]);
	});

	it("waits when the matching row is still an empty shell", () => {
		const rows = [{ role: "assistant", content: "", message_id: "m1" }];
		expect(S._pick_recovery_row(rows, "m1", new Set())).toBeNull();
	});

	it("ignores a finished row belonging to a different turn", () => {
		const rows = [
			{ role: "assistant", content: "old answer", message_id: "m0" },
			{ role: "assistant", content: "", message_id: "m1" },
		];
		expect(S._pick_recovery_row(rows, "m1", new Set())).toBeNull();
	});

	it("falls back to an unseen trailing row when stream_start never arrived", () => {
		const rows = [
			{ role: "user", content: "hi" },
			{ role: "assistant", content: "the answer", message_id: "m1" },
		];
		expect(S._pick_recovery_row(rows, null, new Set(["m0"]))).toBe(rows[1]);
	});

	it("refuses to re-adopt an answer already on screen", () => {
		const rows = [{ role: "assistant", content: "old answer", message_id: "m0" }];
		expect(S._pick_recovery_row(rows, null, new Set(["m0"]))).toBeNull();
	});

	it("refuses the fallback when the trailing row has no id to dedupe on", () => {
		const rows = [{ role: "assistant", content: "old answer" }];
		expect(S._pick_recovery_row(rows, null, new Set())).toBeNull();
	});

	it("waits when the turn is still generating", () => {
		const rows = [{ role: "user", content: "hi" }];
		expect(S._pick_recovery_row(rows, null, new Set())).toBeNull();
		expect(S._pick_recovery_row([], null, new Set())).toBeNull();
	});
});

describe("widget streaming — socket readiness", () => {
	let S, widget;
	beforeEach(() => {
		S = loadStreamingModule();
		widget = makeWidget();
		S._bind_socket_listeners = vi.fn();
	});

	it("binds straight away when the socket is up", () => {
		S.setup_socket_listeners(widget);
		expect(S._bind_socket_listeners).toHaveBeenCalledWith(widget);
	});

	it("waits for a socket that lags script load", () => {
		vi.useFakeTimers();
		globalThis.frappe.realtime.socket = undefined;
		S.setup_socket_listeners(widget);
		expect(S._bind_socket_listeners).not.toHaveBeenCalled();

		vi.advanceTimersByTime(300);
		expect(S._bind_socket_listeners).not.toHaveBeenCalled();

		globalThis.frappe.realtime.socket = { connected: true, connect: vi.fn() };
		vi.advanceTimersByTime(100);
		expect(S._bind_socket_listeners).toHaveBeenCalledWith(widget);
		vi.useRealTimers();
	});

	it("gives up rather than polling forever", () => {
		vi.useFakeTimers();
		globalThis.frappe.realtime.socket = undefined;
		S.setup_socket_listeners(widget);
		vi.advanceTimersByTime(60_000);
		expect(S._bind_socket_listeners).not.toHaveBeenCalled();
		expect(vi.getTimerCount()).toBe(0);
		vi.useRealTimers();
	});
});

describe("widget streaming — recovery wiring", () => {
	let S, widget;
	beforeEach(() => {
		S = loadStreamingModule();
		widget = makeWidget();
	});

	it("listens for connect and disconnect exactly once", () => {
		S.setup_connection_recovery(widget);
		S.setup_connection_recovery(widget);
		const events = globalThis.frappe.realtime.on.mock.calls.map((c) => c[0]);
		expect(events).toEqual(["connect", "disconnect"]);
	});

	it("treats an already-connected socket as the first connection", () => {
		S.setup_connection_recovery(widget);
		expect(S._hasConnected).toBe(true);
	});
});

describe("widget streaming — connect handler", () => {
	let S, widget;
	beforeEach(() => {
		S = loadStreamingModule();
		widget = makeWidget({ _isStreaming: false });
		S.recover_session = vi.fn();
	});

	it("skips recovery on the very first connect", () => {
		S._hasConnected = false;
		S._on_socket_connect(widget);
		expect(S.recover_session).not.toHaveBeenCalled();
	});

	it("recovers on the first connect when a send raced the socket", () => {
		S._hasConnected = false;
		widget._isStreaming = true;
		S._on_socket_connect(widget);
		expect(S.recover_session).toHaveBeenCalledWith(widget);
	});

	it("recovers on every reconnect", () => {
		S._hasConnected = false;
		S._on_socket_connect(widget);
		S._on_socket_connect(widget);
		S._on_socket_connect(widget);
		expect(S.recover_session).toHaveBeenCalledTimes(2);
	});
});

describe("widget streaming — session recovery", () => {
	let S, widget;
	beforeEach(() => {
		S = loadStreamingModule();
		widget = makeWidget();
		S.subscribe_session = vi.fn();
		S.hydrate_pending_interrupt = vi.fn();
		S.reconcile_from_server = vi.fn();
		S.update_processing_status = vi.fn();
	});

	it("re-joins the session room and re-reads server state", () => {
		S.recover_session(widget);
		expect(S.subscribe_session).toHaveBeenCalledWith("faco_1");
		expect(S.hydrate_pending_interrupt).toHaveBeenCalledWith(widget);
		expect(S.reconcile_from_server).toHaveBeenCalledWith(widget);
	});

	it("skips the reconcile when no turn is in flight", () => {
		widget._isStreaming = false;
		S.recover_session(widget);
		expect(S.subscribe_session).toHaveBeenCalledWith("faco_1");
		expect(S.reconcile_from_server).not.toHaveBeenCalled();
	});

	it("does nothing without a session", () => {
		S.recover_session(makeWidget({ session_id: null }));
		expect(S.subscribe_session).not.toHaveBeenCalled();
	});
});

describe("widget streaming — reconcile from server", () => {
	let S, widget;
	beforeEach(() => {
		S = loadStreamingModule();
		widget = makeWidget();
		S._adopt_server_answer = vi.fn();
	});

	it("adopts the answer that landed while the socket was down", async () => {
		widget.current_message_id = "m1";
		S._fetch_session_messages = vi
			.fn()
			.mockResolvedValue([{ role: "assistant", content: "the answer", message_id: "m1" }]);
		expect(await S.reconcile_from_server(widget)).toBe(true);
		expect(S._adopt_server_answer).toHaveBeenCalled();
	});

	it("leaves the turn alone when the server has nothing new", async () => {
		widget.current_message_id = "m1";
		S._fetch_session_messages = vi
			.fn()
			.mockResolvedValue([{ role: "assistant", content: "", message_id: "m1" }]);
		expect(await S.reconcile_from_server(widget)).toBe(false);
		expect(S._adopt_server_answer).not.toHaveBeenCalled();
	});

	it("drops the result when the user switched sessions mid-fetch", async () => {
		widget.current_message_id = "m1";
		S._fetch_session_messages = vi.fn().mockImplementation(() => {
			widget.session_id = "faco_2";
			return Promise.resolve([{ role: "assistant", content: "the answer", message_id: "m1" }]);
		});
		expect(await S.reconcile_from_server(widget)).toBe(false);
		expect(S._adopt_server_answer).not.toHaveBeenCalled();
	});

	it("does not adopt an answer the live stream already finalized", async () => {
		widget.current_message_id = "m1";
		S._fetch_session_messages = vi.fn().mockImplementation(() => {
			widget._isStreaming = false; // stream_complete landed during the fetch
			return Promise.resolve([{ role: "assistant", content: "the answer", message_id: "m1" }]);
		});
		expect(await S.reconcile_from_server(widget)).toBe(false);
		expect(S._adopt_server_answer).not.toHaveBeenCalled();
	});

	it("survives a failed history read", async () => {
		S._fetch_session_messages = vi.fn().mockRejectedValue(new Error("offline"));
		expect(await S.reconcile_from_server(widget)).toBe(false);
	});

	it("does not stack concurrent reconciles", async () => {
		S._fetch_session_messages = vi.fn().mockResolvedValue([]);
		const [a, b] = await Promise.all([
			S.reconcile_from_server(widget),
			S.reconcile_from_server(widget),
		]);
		expect(a || b).toBe(false);
		expect(S._fetch_session_messages).toHaveBeenCalledTimes(1);
	});
});

describe("widget streaming — adopting a server answer", () => {
	let S, widget;
	beforeEach(() => {
		S = loadStreamingModule();
		widget = makeWidget();
		S._fail_turn = vi.fn();
		S.finalize_streaming_message = vi.fn();
		S._release_composer = vi.fn();
	});

	it("renders the server's complete text into the live bubble", () => {
		const data = vi.fn();
		widget.$widget = { find: () => ({ length: 1, find: () => ({ data }) }) };
		S._adopt_server_answer(widget, { content: "the answer", message_id: "m1" });
		expect(data).toHaveBeenCalledWith("raw-markdown", "the answer");
		expect(S.finalize_streaming_message).toHaveBeenCalledWith(widget, "the answer", 0, null);
		expect(widget._isStreaming).toBe(false);
		expect(widget._seenMessageIds.has("m1")).toBe(true);
	});

	it("appends the answer when the bubble was already wiped", () => {
		S._adopt_server_answer(widget, { content: "the answer", message_id: "m1" });
		expect(widget.add_message_to_ui).toHaveBeenCalledWith("assistant", "the answer");
		expect(widget.messages).toEqual([{ role: "assistant", content: "the answer" }]);
	});

	it("shows a notice for a terminal row with no text to render", () => {
		S._adopt_server_answer(widget, { content: "", aborted: 1, message_id: "m1" });
		expect(S._fail_turn).toHaveBeenCalledWith(widget, "Response stopped.", "");
		expect(S.finalize_streaming_message).not.toHaveBeenCalled();
	});
});

describe("widget streaming — timeout", () => {
	let S, widget;
	beforeEach(() => {
		S = loadStreamingModule();
		widget = makeWidget();
		S._fail_turn = vi.fn();
		S.update_processing_status = vi.fn();
	});

	it("recovers a turn that actually succeeded instead of reporting failure", async () => {
		S.reconcile_from_server = vi.fn().mockResolvedValue(true);
		await S.handle_stream_timeout(widget, "No response received.");
		expect(S._fail_turn).not.toHaveBeenCalled();
	});

	it("gives a dead socket one more window before giving up", async () => {
		S.reconcile_from_server = vi.fn().mockResolvedValue(false);
		globalThis.frappe.realtime.socket.connected = false;
		await S.handle_stream_timeout(widget, "stalled", { allowRetry: true });
		expect(globalThis.frappe.realtime.socket.connect).toHaveBeenCalled();
		expect(S._fail_turn).not.toHaveBeenCalled();
		expect(S._activityTimeoutId).not.toBeNull();
		S.clear_timeouts();
	});

	it("fails the turn once the grace window is spent", async () => {
		S.reconcile_from_server = vi.fn().mockResolvedValue(false);
		globalThis.frappe.realtime.socket.connected = false;
		await S.handle_stream_timeout(widget, "stalled");
		expect(S._fail_turn).toHaveBeenCalled();
	});

	it("fails immediately on a live socket with nothing to recover", async () => {
		S.reconcile_from_server = vi.fn().mockResolvedValue(false);
		await S.handle_stream_timeout(widget, "stalled", { allowRetry: true });
		expect(S._fail_turn).toHaveBeenCalled();
	});
});
