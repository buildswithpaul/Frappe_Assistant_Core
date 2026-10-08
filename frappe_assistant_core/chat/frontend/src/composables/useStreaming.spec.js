import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { createSpaConnectHandler, createVisibilityHandler, useStreaming } from "./useStreaming";
import { useChatStore } from "@/stores/chatStore";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			getMessages: vi.fn().mockResolvedValue([]),
			getLiveTurn: vi.fn().mockResolvedValue(null),
			send: vi.fn().mockResolvedValue({}),
		},
		get: vi.fn().mockResolvedValue({}),
	},
}));

vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

vi.mock("socket.io-client", () => {
	const fakeSocket = {
		connected: false,
		on: vi.fn(),
		off: vi.fn(),
		emit: vi.fn(),
		connect: vi.fn(),
		io: { on: vi.fn() },
	};
	return { io: vi.fn(() => fakeSocket), __fakeSocket: fakeSocket };
});
import * as socketIoMock from "socket.io-client";

function makeChatStore(sessionId = "session-1") {
	return {
		currentSessionId: sessionId,
		isStreaming: false,
		setSocketConnected: vi.fn(),
		hydratePendingInterrupt: vi.fn(),
		recoverLiveTurn: vi.fn(),
	};
}

describe("createVisibilityHandler", () => {
	let chatStore;
	let socket;

	function setVisibility(state) {
		Object.defineProperty(document, "visibilityState", {
			configurable: true,
			get: () => state,
		});
	}

	beforeEach(() => {
		chatStore = makeChatStore("s-vis");
		socket = { connected: true, emit: vi.fn(), connect: vi.fn() };
		setVisibility("visible");
	});

	// jsdom's document is shared across this file, so the override has to go
	// or later suites inherit it.
	afterEach(() => {
		delete document.visibilityState;
	});

	it("recovers an in-flight turn on a socket that stayed connected while throttled", () => {
		chatStore.isStreaming = true;
		createVisibilityHandler(chatStore, () => socket)();

		expect(socket.connect).not.toHaveBeenCalled();
		expect(socket.emit).toHaveBeenCalledWith("task_subscribe", "s-vis");
		expect(chatStore.recoverLiveTurn).toHaveBeenCalledWith("s-vis");
	});

	it("leaves an idle tab alone", () => {
		createVisibilityHandler(chatStore, () => socket)();

		expect(socket.emit).not.toHaveBeenCalled();
		expect(chatStore.recoverLiveTurn).not.toHaveBeenCalled();
	});

	it("revives a dead socket and lets the connect handler do the recovery", () => {
		socket.connected = false;
		chatStore.isStreaming = true;
		createVisibilityHandler(chatStore, () => socket)();

		expect(socket.connect).toHaveBeenCalledTimes(1);
		expect(socket.emit).not.toHaveBeenCalled();
	});

	it("does nothing while the tab is hidden", () => {
		Object.defineProperty(document, "visibilityState", {
			configurable: true,
			get: () => "hidden",
		});
		chatStore.isStreaming = true;
		createVisibilityHandler(chatStore, () => socket)();

		expect(socket.connect).not.toHaveBeenCalled();
		expect(socket.emit).not.toHaveBeenCalled();
	});
});

describe("createSpaConnectHandler", () => {
	let chatStore;
	let socket;
	let handler;

	beforeEach(() => {
		chatStore = makeChatStore();
		socket = { emit: vi.fn() };
		handler = createSpaConnectHandler(chatStore, socket);
	});

	it("skips recovery on the first connection (initial hydration is useChatViewInit's job)", () => {
		handler();

		expect(chatStore.setSocketConnected).toHaveBeenCalledWith(true);
		expect(socket.emit).not.toHaveBeenCalled();
		expect(chatStore.hydratePendingInterrupt).not.toHaveBeenCalled();
		expect(chatStore.recoverLiveTurn).not.toHaveBeenCalled();
	});

	it("re-joins the session room and reconciles on every re-connection", () => {
		handler(); // first connect
		handler(); // reconnect

		expect(socket.emit).toHaveBeenCalledTimes(1);
		expect(socket.emit).toHaveBeenCalledWith("task_subscribe", "session-1");
		expect(chatStore.hydratePendingInterrupt).toHaveBeenCalledWith("session-1");
		expect(chatStore.recoverLiveTurn).toHaveBeenCalledWith("session-1");

		handler(); // second reconnect recovers again
		expect(socket.emit).toHaveBeenCalledTimes(2);
		expect(chatStore.recoverLiveTurn).toHaveBeenCalledTimes(2);
	});

	it("reads the session id at reconnect time, not registration time", () => {
		handler();
		chatStore.currentSessionId = "session-2";
		handler();

		expect(socket.emit).toHaveBeenCalledWith("task_subscribe", "session-2");
		expect(chatStore.recoverLiveTurn).toHaveBeenCalledWith("session-2");
	});

	it("recovers on the FIRST connection when a turn is already in flight (send raced the socket)", () => {
		chatStore.isStreaming = true;
		handler();

		expect(socket.emit).toHaveBeenCalledWith("task_subscribe", "session-1");
		expect(chatStore.recoverLiveTurn).toHaveBeenCalledWith("session-1");
	});

	it("does nothing beyond connection state when no session is active", () => {
		chatStore.currentSessionId = null;
		handler();
		handler();

		expect(chatStore.setSocketConnected).toHaveBeenCalledTimes(2);
		expect(socket.emit).not.toHaveBeenCalled();
		expect(chatStore.recoverLiveTurn).not.toHaveBeenCalled();
	});
});

describe("SPA socket wiring", () => {
	// One sequential test: the module holds a singleton socket, so mount once
	// and assert the full wiring — this is the exact registration that was
	// broken (recovery listened on the Socket's never-firing "reconnect").
	it("registers recovery on 'connect', reconnect lifecycle on the Manager, and the visibility nudge", async () => {
		const fake = socketIoMock.__fakeSocket;
		const pinia = createPinia();
		const Dummy = defineComponent({
			setup() {
				useStreaming();
				return () => null;
			},
		});
		mount(Dummy, { global: { plugins: [pinia] } });

		// Recovery must NOT hang off the Socket's "reconnect" (dead in v4).
		const socketEvents = fake.on.mock.calls.map((c) => c[0]);
		expect(socketEvents).toContain("connect");
		expect(socketEvents).not.toContain("reconnect");

		// Reconnect lifecycle listeners live on the Manager.
		const managerEvents = fake.io.on.mock.calls.map((c) => c[0]);
		expect(managerEvents).toEqual(
			expect.arrayContaining(["reconnect_attempt", "reconnect", "reconnect_failed"])
		);

		// Firing "connect" twice performs recovery (room re-join) on the second.
		const chatStore = useChatStore(pinia);
		chatStore.currentSessionId = "s-wire";
		const connectHandler = fake.on.mock.calls.find((c) => c[0] === "connect")[1];
		connectHandler();
		expect(fake.emit).not.toHaveBeenCalledWith("task_subscribe", "s-wire");
		connectHandler();
		expect(fake.emit).toHaveBeenCalledWith("task_subscribe", "s-wire");

		// Foregrounding the tab revives a dead socket…
		fake.connected = false;
		document.dispatchEvent(new Event("visibilitychange"));
		expect(fake.connect).toHaveBeenCalledTimes(1);

		// …but leaves a healthy one alone.
		fake.connected = true;
		document.dispatchEvent(new Event("visibilitychange"));
		expect(fake.connect).toHaveBeenCalledTimes(1);
	});
});

describe("browser_navigate_to hand-off", () => {
	let handler;
	let hrefSet;
	let originalLocation;

	beforeEach(async () => {
		const { resetSurface } = await import("@/stores/chat/surface");
		resetSurface();
		sessionStorage.clear();
		vi.useFakeTimers();
		// Desk's realtime client: the same path production takes on a Frappe page.
		window.frappe = {
			realtime: {
				on: vi.fn((name, fn) => {
					if (name === "faco_message_stream") handler = fn;
				}),
				off: vi.fn(),
				task_subscribe: vi.fn(),
				task_unsubscribe: vi.fn(),
			},
		};
		originalLocation = window.location;
		hrefSet = vi.fn();
		Object.defineProperty(window, "location", {
			configurable: true,
			value: {
				origin: "http://localhost",
				get href() {
					return "http://localhost/";
				},
				set href(v) {
					hrefSet(v);
				},
			},
		});
	});

	afterEach(async () => {
		const { resetSurface } = await import("@/stores/chat/surface");
		resetSurface();
		Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
		delete window.frappe;
		vi.useRealTimers();
	});

	function fireNavigate() {
		const pinia = createPinia();
		mount(
			defineComponent({
				setup() {
					useStreaming();
					return () => null;
				},
			}),
			{ global: { plugins: [pinia] } }
		);
		const chatStore = useChatStore(pinia);
		chatStore.currentSessionId = "s-nav";
		handler({
			event: "tool_call_start",
			session_id: "s-nav",
			tool_name: "browser_navigate_to",
			tool_id: "t1",
			input: { url: "/app/todo" },
		});
		vi.advanceTimersByTime(1000);
	}

	it("hard-navigates and stores the hand-off on the SPA", () => {
		fireNavigate();
		expect(hrefSet).toHaveBeenCalledWith("/app/todo");
		expect(sessionStorage.getItem("faco_widget_session")).toContain("s-nav");
	});

	it("leaves Desk alone in the widget: the launcher's navigate_to already routed", async () => {
		const { configureSurface } = await import("@/stores/chat/surface");
		configureSurface({ name: "widget", clientType: "widget" });
		fireNavigate();
		expect(hrefSet).not.toHaveBeenCalled();
		expect(sessionStorage.getItem("faco_widget_session")).toBeNull();
	});
});

describe("live-turn gate on the realtime dispatcher", () => {
	let handler;
	let store;
	let api;

	beforeEach(async () => {
		({ api } = await import("@/api/client"));
		vi.clearAllMocks();
		// Desk's realtime client: the same path production takes on a Frappe page.
		window.frappe = {
			realtime: {
				on: vi.fn((name, fn) => {
					if (name === "faco_message_stream") handler = fn;
				}),
				off: vi.fn(),
				task_subscribe: vi.fn(),
				task_unsubscribe: vi.fn(),
			},
		};
		const pinia = createPinia();
		mount(
			defineComponent({
				setup() {
					useStreaming();
					return () => null;
				},
			}),
			{ global: { plugins: [pinia] } }
		);
		store = useChatStore(pinia);
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "Count the orders" },
			{ role: "assistant", message_id: "m1", content: "", blocks: null },
		]);
	});

	afterEach(() => {
		delete window.frappe;
	});

	const chunk = (seq, text) => ({
		event: "stream_chunk", session_id: "s-gate", turn: "T1", client_turn: "other", seq, chunk: text,
	});

	it("holds a numbered event while the snapshot is read, then applies it once after the snapshot", async () => {
		let resolveSnapshot;
		api.chat.getLiveTurn.mockReturnValue(new Promise((r) => (resolveSnapshot = r)));
		const loading = store.loadMessages("s-gate");
		await vi.waitFor(() => expect(api.chat.getLiveTurn).toHaveBeenCalled());

		handler(chunk(5, "12."));
		expect(store.streamingMessage).toBe("");

		resolveSnapshot({
			turn: "T1", seq: 4, message_id: "m1", status: "streaming", text: "There are ",
			blocks: [{ type: "text", id: "tx1", content: "There are " }], active_thinking_id: null,
		});
		await loading;

		expect(store.messages[1].content).toBe("There are 12.");
		expect(store.streamingMessage).toBe("There are 12.");
		// A re-delivery of the same event is dropped, so nothing is applied twice.
		handler(chunk(5, "12."));
		expect(store.messages[1].content).toBe("There are 12.");
	});

	it("keeps streaming onto the joined answer through the dispatcher", async () => {
		api.chat.getLiveTurn.mockResolvedValue({
			turn: "T1", seq: 4, message_id: "m1", status: "streaming", text: "There are ",
			blocks: [{ type: "text", id: "tx1", content: "There are " }], active_thinking_id: null,
		});
		await store.loadMessages("s-gate");
		handler(chunk(5, "12."));
		expect(store.messages[1].content).toBe("There are 12.");
	});

	// Live round 3 (L4): AR sends the resume's stream_start before it waits on
	// the session lock, so the paused turn's own stream_complete(interrupted)
	// arrives after the resume began. Finishing the streaming state on it
	// stopped the watchdog and opened the send queue while the resume ran.
	it("lets a superseded turn's late stream_complete leave the resume streaming", async () => {
		store.currentSessionId = "s-gate";
		api.chat.getLiveTurn.mockResolvedValue(null);
		await store.sendMessage("Create a ToDo");
		const paused = store.messages.at(-1);
		const sent = paused._requestId;
		const t1 = (seq, extra) => ({ session_id: "s-gate", turn: "T1", client_turn: sent, seq, ...extra });

		handler(t1(1, { event: "stream_start", message_id: "m1" }));
		handler(t1(2, { event: "approval_required", tool_id: "call_1", tool_name: "create_document", interrupts: [{ id: "int1" }] }));
		await store.submitInterruptDecision({ blockId: "call_1", resolution: "approved", userResponse: null, response: "approve" });
		const resumed = paused._requestId;
		expect(resumed).not.toBe(sent);
		handler({ event: "stream_start", session_id: "s-gate", turn: "T2", client_turn: resumed, seq: 1, message_id: "m1", resumed: true });
		expect(store.isStreaming).toBe(true);

		handler(t1(3, { event: "stream_complete", interrupted: true, full_response: "", blocks: [] }));

		expect(store.isStreaming).toBe(true);
		expect(paused.isStreaming).toBe(true);
		await store.sendMessage("And another");
		expect(store.queuedMessages).toHaveLength(1);
	});

	it("stops dispatching to an unmounted composable", async () => {
		const pinia = createPinia();
		const wrapper = mount(
			defineComponent({
				setup() {
					useStreaming();
					return () => null;
				},
			}),
			{ global: { plugins: [pinia] } }
		);
		const other = useChatStore(pinia);
		const spy = vi.spyOn(other, "setStreamDispatcher");
		wrapper.unmount();
		expect(spy).toHaveBeenCalledWith(null);
	});
});
