import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "../chatStore";

vi.mock("@/api/client", () => ({ api: { chat: {} } }));

describe("chatStore first-message handoff", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("returns the queued text once", () => {
		const store = useChatStore();
		store.queueFirstMessage("s1", "hello");
		expect(store.takeFirstMessage("s1")).toBe("hello");
		expect(store.takeFirstMessage("s1")).toBe(null);
	});

	it("only returns the message for its own session", () => {
		const store = useChatStore();
		store.queueFirstMessage("s1", "hello");
		expect(store.takeFirstMessage("s2")).toBe(null);
		expect(store.takeFirstMessage("s1")).toBe("hello");
	});
});
