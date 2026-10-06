import { describe, it, expect, vi, afterEach } from "vitest";
import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createSocketProbe, useStreaming } from "./useStreaming";
import { useChatStore } from "@/stores/chatStore";

vi.mock("@/api/client", () => ({
	api: { chat: { getMessages: vi.fn().mockResolvedValue([]) }, get: vi.fn().mockResolvedValue({}) },
}));

describe("createSocketProbe", () => {
	it("reads connected from the live socket and nudges via connect()", () => {
		const socket = { connected: false, connect: vi.fn() };
		const probe = createSocketProbe(() => socket);

		expect(probe.connected()).toBe(false);
		probe.nudge();
		expect(socket.connect).toHaveBeenCalledTimes(1);

		socket.connected = true;
		expect(probe.connected()).toBe(true);
	});

	it("treats a missing socket as disconnected and nudges nothing", () => {
		const probe = createSocketProbe(() => undefined);
		expect(probe.connected()).toBe(false);
		expect(() => probe.nudge()).not.toThrow();
	});
});

describe("useStreaming on the frappe.realtime path", () => {
	afterEach(() => {
		delete window.frappe;
	});

	it("registers a probe over window.frappe.realtime.socket", () => {
		const socket = { connected: false, connect: vi.fn() };
		window.frappe = { realtime: { on: vi.fn(), off: vi.fn(), socket } };
		window.frappe.realtime.task_subscribe = vi.fn();

		const pinia = createPinia();
		setActivePinia(pinia);
		const chatStore = useChatStore(pinia);
		const setProbe = vi.spyOn(chatStore, "setSocketProbe");
		const Dummy = defineComponent({
			setup() {
				useStreaming();
				return () => null;
			},
		});
		mount(Dummy, { global: { plugins: [pinia] } });

		expect(setProbe).toHaveBeenCalledTimes(1);
		const probe = setProbe.mock.calls[0][0];
		expect(probe.connected()).toBe(false);
		probe.nudge();
		expect(socket.connect).toHaveBeenCalledTimes(1);
		socket.connected = true;
		expect(probe.connected()).toBe(true);
	});

	it("clears the reconnecting indicator when the realtime socket reconnects", () => {
		const on = vi.fn();
		window.frappe = { realtime: { on, off: vi.fn(), socket: { connected: true } } };
		const pinia = createPinia();
		setActivePinia(pinia);
		const chatStore = useChatStore(pinia);
		const Dummy = defineComponent({
			setup() {
				useStreaming();
				return () => null;
			},
		});
		mount(Dummy, { global: { plugins: [pinia] } });

		// Production raises the indicator after a sustained disconnect (or a grace).
		vi.useFakeTimers();
		chatStore.handleSocketDisconnect("transport close");
		vi.advanceTimersByTime(3000);
		vi.useRealTimers();
		expect(chatStore.connectionVisible).toBe(true);
		const connect = on.mock.calls.find((c) => c[0] === "connect")[1];
		connect();

		expect(chatStore.socketConnected).toBe(true);
		expect(chatStore.connectionVisible).toBe(false);
	});
});
