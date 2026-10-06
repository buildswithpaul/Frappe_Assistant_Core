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
});
