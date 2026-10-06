import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "../chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			getMessages: vi.fn(),
			continueResponse: vi.fn().mockResolvedValue({ success: true }),
		},
	},
}));

const WINDOW_MS = 180000;
const STILL_RUNNING = [{ role: "user", content: "hi" }];

function makeProbe(connected) {
	const probe = { up: connected, nudge: vi.fn(), connected: () => probe.up };
	return probe;
}

async function elapseWindow() {
	await vi.advanceTimersByTimeAsync(WINDOW_MS);
}

describe("stream manager dead-socket grace window", () => {
	let store;

	beforeEach(() => {
		vi.useFakeTimers();
		setActivePinia(createPinia());
		store = useChatStore();
		vi.clearAllMocks();
		api.chat.getMessages.mockResolvedValue(STILL_RUNNING);
		store.currentSessionId = "s1";
		store.isStreaming = true;
		store.messages = [
			{ role: "user", content: "hi" },
			{ role: "assistant", message_id: "m1", isStreaming: true, content: "", blocks: [] },
		];
	});

	afterEach(() => {
		store.clearStreamTimeouts?.();
		vi.useRealTimers();
	});

	it("nudges a dead socket once and fails only after a second silent window", async () => {
		const probe = makeProbe(false);
		store.setSocketProbe(probe);
		store.resetActivityTimeout();

		await elapseWindow();
		expect(probe.nudge).toHaveBeenCalledTimes(1);
		expect(store.error).toBeNull();
		expect(store.isStreaming).toBe(true);

		await elapseWindow();
		expect(probe.nudge).toHaveBeenCalledTimes(1);
		expect(store.error).toMatch(/No response received/);
		expect(store.isStreaming).toBe(false);
	});

	it("re-earns the grace after activity arrives during the grace window", async () => {
		const probe = makeProbe(false);
		store.setSocketProbe(probe);
		store.resetActivityTimeout();

		await elapseWindow();
		expect(probe.nudge).toHaveBeenCalledTimes(1);

		store.resetActivityTimeout();
		await elapseWindow();
		expect(probe.nudge).toHaveBeenCalledTimes(2);
		expect(store.error).toBeNull();
		expect(store.isStreaming).toBe(true);
	});

	it("fails immediately when the socket is connected", async () => {
		const probe = makeProbe(true);
		store.setSocketProbe(probe);
		store.resetActivityTimeout();

		await elapseWindow();
		expect(probe.nudge).not.toHaveBeenCalled();
		expect(store.error).toMatch(/No response received/);
		expect(store.isStreaming).toBe(false);
	});

	it("fails immediately when no probe is registered", async () => {
		store.resetActivityTimeout();

		await elapseWindow();
		expect(store.error).toMatch(/No response received/);
		expect(store.isStreaming).toBe(false);
	});

	it("does not nudge or fail when reconcile adopts the finished turn", async () => {
		const probe = makeProbe(false);
		store.setSocketProbe(probe);
		api.chat.getMessages.mockResolvedValue([
			{ role: "user", content: "hi" },
			{ role: "assistant", message_id: "m1", content: "done", blocks: "[]" },
		]);
		store.resetActivityTimeout();

		await elapseWindow();
		expect(probe.nudge).not.toHaveBeenCalled();
		expect(store.error).toBeNull();
		expect(store.isStreaming).toBe(false);
	});

	it("clears the reconnecting indicator when a stream event arrives after a grace", async () => {
		store.setSocketProbe(makeProbe(false));
		store.resetActivityTimeout();
		await elapseWindow();
		expect(store.connectionVisible).toBe(true);

		store.resetActivityTimeout();
		expect(store.connectionVisible).toBe(false);
	});

	it("gives a new turn a fresh grace", async () => {
		const probe = makeProbe(false);
		store.setSocketProbe(probe);
		store.resetActivityTimeout();
		await elapseWindow();
		expect(probe.nudge).toHaveBeenCalledTimes(1);

		// Grace spent, then the turn ends and the user continues a truncated
		// answer: continueMessage starts a new turn via startStreamTimeout.
		store.isStreaming = false;
		store.messages = [
			{ role: "assistant", message_id: "m2", content: "cut", truncated: true, blocks: [] },
		];
		await store.continueMessage("m2");
		await elapseWindow();
		expect(probe.nudge).toHaveBeenCalledTimes(2);
		expect(store.error).toBeNull();
	});

	it("keeps a disconnected banner when a turn starts while the socket is still down", async () => {
		// Production: the SPA socket drops, the 3 s debounce raises the banner,
		// and the user then sends over HTTP.
		store.isStreaming = false;
		store.handleSocketDisconnect("transport close");
		await vi.advanceTimersByTimeAsync(3000);
		expect(store.connectionVisible).toBe(true);

		store.messages = [
			{ role: "assistant", message_id: "m2", content: "cut", truncated: true, blocks: [] },
		];
		await store.continueMessage("m2");

		expect(store.connectionVisible).toBe(true);
	});
});
