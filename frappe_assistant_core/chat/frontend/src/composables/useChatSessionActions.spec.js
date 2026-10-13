import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatSessionActions } from "@/composables/useChatSessionActions";
import { useConversationsStore } from "@/stores/conversationsStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({ api: { chat: { deleteSession: vi.fn().mockResolvedValue({}) } } }));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

describe("handleDeleteSession", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("also removes an archived chat from the search results", async () => {
		const conversations = useConversationsStore();
		conversations.searchResults = [{ session_id: "a" }, { session_id: "b" }];
		const chatStore = {
			removeSession: vi.fn(),
			currentSessionId: "b",
			sessions: [{ session_id: "b" }],
			sortedSessions: [],
		};
		const { handleDeleteSession } = useChatSessionActions({
			chatStore,
			router: { push: vi.fn() },
			handleNewChat: vi.fn(),
		});
		await handleDeleteSession("a");
		expect(api.chat.deleteSession).toHaveBeenCalledWith("a");
		expect(conversations.searchResults.map((s) => s.session_id)).toEqual(["b"]);
	});
});
