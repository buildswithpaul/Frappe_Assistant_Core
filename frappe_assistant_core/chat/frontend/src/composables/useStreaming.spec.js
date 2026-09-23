import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { createSpaConnectHandler, createVisibilityHandler, useStreaming } from "./useStreaming";
import { useChatStore } from "@/stores/chatStore";

vi.mock("@/api/client", () => ({
	api: {
		chat: { getMessages: vi.fn().mockResolvedValue([]) },
		get: vi.fn().mockResolvedValue({}),
	},
}));

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
		reconcileFromServer: vi.fn(),
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
		expect(chatStore.reconcileFromServer).toHaveBeenCalledWith("s-vis");
	});

	it("leaves an idle tab alone", () => {
		createVisibilityHandler(chatStore, () => socket)();

		expect(socket.emit).not.toHaveBeenCalled();
		expect(chatStore.reconcileFromServer).not.toHaveBeenCalled();
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
		expect(chatStore.reconcileFromServer).not.toHaveBeenCalled();
	});

	it("re-joins the session room and reconciles on every re-connection", () => {
		handler(); // first connect
		handler(); // reconnect

		expect(socket.emit).toHaveBeenCalledTimes(1);
		expect(socket.emit).toHaveBeenCalledWith("task_subscribe", "session-1");
		expect(chatStore.hydratePendingInterrupt).toHaveBeenCalledWith("session-1");
		expect(chatStore.reconcileFromServer).toHaveBeenCalledWith("session-1");

		handler(); // second reconnect recovers again
		expect(socket.emit).toHaveBeenCalledTimes(2);
		expect(chatStore.reconcileFromServer).toHaveBeenCalledTimes(2);
	});

	it("reads the session id at reconnect time, not registration time", () => {
		handler();
		chatStore.currentSessionId = "session-2";
		handler();

		expect(socket.emit).toHaveBeenCalledWith("task_subscribe", "session-2");
		expect(chatStore.reconcileFromServer).toHaveBeenCalledWith("session-2");
	});

	it("recovers on the FIRST connection when a turn is already in flight (send raced the socket)", () => {
		chatStore.isStreaming = true;
		handler();

		expect(socket.emit).toHaveBeenCalledWith("task_subscribe", "session-1");
		expect(chatStore.reconcileFromServer).toHaveBeenCalledWith("session-1");
	});

	it("does nothing beyond connection state when no session is active", () => {
		chatStore.currentSessionId = null;
		handler();
		handler();

		expect(chatStore.setSocketConnected).toHaveBeenCalledTimes(2);
		expect(socket.emit).not.toHaveBeenCalled();
		expect(chatStore.reconcileFromServer).not.toHaveBeenCalled();
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
