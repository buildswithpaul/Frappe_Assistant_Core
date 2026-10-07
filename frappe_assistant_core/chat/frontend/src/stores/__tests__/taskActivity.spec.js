import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";

vi.mock("@/api/client", () => ({
	api: {
		chat: {
			send: vi.fn().mockResolvedValue({}),
			cancelStream: vi.fn().mockResolvedValue({}),
			getMessages: vi.fn().mockResolvedValue({ messages: [] }),
		},
	},
}));

describe("task activity labels", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
	});

	it("records the latest label per task while streaming", async () => {
		await store.sendMessage("Compare customers A and B", [], null, "m1");

		store.handleTaskActivity({ task_id: "t-1", label: "x" });
		store.handleTaskActivity({ task_id: "t-2", label: "y" });
		store.handleTaskActivity({ task_id: "t-1", label: "z" });

		expect(store.taskActivity).toEqual({ "t-1": "z", "t-2": "y" });
	});

	it("ignores an event without a task_id", () => {
		store.handleTaskActivity({ label: "orphan" });
		expect(store.taskActivity).toEqual({});
	});

	it("clears every label when the stream ends", async () => {
		await store.sendMessage("Compare customers A and B", [], null, "m1");
		store.handleTaskActivity({ task_id: "t-1", label: "x" });
		expect(store.taskActivity["t-1"]).toBe("x");

		await store.abortStream();

		expect(store.taskActivity).toEqual({});
	});

	it("clears every label when the turn completes", async () => {
		await store.sendMessage("Compare customers A and B", [], null, "m1");
		store.handleTaskActivity({ task_id: "t-1", label: "x" });

		store.completeStreaming("Done.");

		expect(store.taskActivity).toEqual({});
	});

	it("drops the previous session's labels when another session loads", async () => {
		await store.sendMessage("Compare customers A and B", [], null, "m1");
		store.handleTaskActivity({ task_id: "t-1", label: "x" });
		expect(store.isStreaming).toBe(true);

		await store.loadMessages("s2");

		expect(store.taskActivity).toEqual({});
	});

	it("remembers which task reported last, even within one tick", async () => {
		await store.sendMessage("Compare customers A and B", [], null, "m1");
		store.handleTaskActivity({ task_id: "t-1", label: "x" });
		store.handleTaskActivity({ task_id: "t-2", label: "y" });
		store.handleTaskActivity({ task_id: "t-1", label: "z" });

		expect(store.lastActivityTaskId).toBe("t-1");
	});

	it("forgets the last reporter with the labels", async () => {
		await store.sendMessage("Compare customers A and B", [], null, "m1");
		store.handleTaskActivity({ task_id: "t-1", label: "x" });
		store.completeStreaming("Done.");
		expect(store.lastActivityTaskId).toBeNull();

		await store.sendMessage("Again", [], null, "m2");
		store.handleTaskActivity({ task_id: "t-2", label: "y" });
		await store.loadMessages("s2");
		expect(store.lastActivityTaskId).toBeNull();

		store.lastActivityTaskId = "t-3";
		store.clearSessions();
		expect(store.lastActivityTaskId).toBeNull();
	});
});

