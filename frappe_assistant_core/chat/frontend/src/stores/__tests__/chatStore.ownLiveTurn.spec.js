import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

// A request FACO makes back to the browser (the page screenshot) reaches every tab in the
// conversation's room; only the tab that sent the live turn may answer it.
vi.mock("@/api/client", () => ({ api: { chat: { send: vi.fn() } } }));
vi.mock("frappe-ui", () => ({ call: vi.fn() }));

describe("isOwnLiveTurn", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		vi.clearAllMocks();
		api.chat.send.mockReturnValue(new Promise(() => {}));
		store = useChatStore();
		store.currentSessionId = "s1";
	});

	it("is true while the turn this tab sent is streaming", () => {
		store.sendMessage("Show me the page", [], null, "m1");
		expect(store.isOwnLiveTurn("s1")).toBe(true);
		expect(store.isOwnLiveTurn("s2")).toBe(false);
	});

	it("is false once the turn completes", () => {
		store.sendMessage("Show me the page", [], null, "m1");
		store.completeStreaming("Done.", {});
		expect(store.isOwnLiveTurn("s1")).toBe(false);
	});

	it("is false for a turn another tab sent, which this tab only watches", () => {
		// A watching tab learns of the turn from its stream; it never set a request id of its own.
		store.messages.push({ role: "assistant", content: "", blocks: [], isStreaming: true, _requestId: null });
		expect(store.isOwnLiveTurn("s1")).toBe(false);
	});
});
