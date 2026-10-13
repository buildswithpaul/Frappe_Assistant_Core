import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useConversationsStore } from "@/stores/conversationsStore";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { chat: { getSessions: vi.fn(), renameSession: vi.fn(), moveSessionToProject: vi.fn() } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

describe("conversationsStore", () => {
	let store, chat;
	beforeEach(() => {
		vi.useFakeTimers();
		setActivePinia(createPinia());
		store = useConversationsStore();
		chat = useChatStore();
		chat.sessions = [{ session_id: "a", title: "Old", preview: "Old", project: null }];
		vi.clearAllMocks();
	});
	afterEach(() => vi.useRealTimers());

	it("debounces search by 300 ms and ignores one-character queries", async () => {
		api.chat.getSessions.mockResolvedValue([{ session_id: "a" }]);
		store.setSearch("z");
		store.setSearch("ze");
		store.setSearch("zebra");
		await vi.advanceTimersByTimeAsync(299);
		expect(api.chat.getSessions).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(1);
		expect(api.chat.getSessions).toHaveBeenCalledTimes(1);
		expect(api.chat.getSessions).toHaveBeenCalledWith({ limit: 50, search: "zebra" });
		store.setSearch("z");
		await vi.advanceTimersByTimeAsync(300);
		expect(store.searchResults).toEqual([]);
	});

	it("renames optimistically and keeps the server's title", async () => {
		api.chat.renameSession.mockResolvedValue({ success: true, title: "New", title_is_custom: true });
		const pending = store.renameSession("a", "New ");
		expect(chat.sessions[0].title).toBe("New ");
		await pending;
		expect(chat.sessions[0]).toMatchObject({ title: "New", preview: "New", title_is_custom: true });
	});

	it("rolls a failed rename back and rethrows", async () => {
		api.chat.renameSession.mockRejectedValue(new Error("nope"));
		await expect(store.renameSession("a", "New")).rejects.toThrow("nope");
		expect(chat.sessions[0].title).toBe("Old");
	});

	it("moves a chat and records the project title", async () => {
		api.chat.moveSessionToProject.mockResolvedValue({ success: true, project: "p1", project_title: "Q3" });
		await store.moveSession("a", "p1");
		expect(chat.sessions[0]).toMatchObject({ project: "p1", project_title: "Q3" });
	});
});
