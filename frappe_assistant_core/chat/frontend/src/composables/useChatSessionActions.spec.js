import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatSessionActions } from "@/composables/useChatSessionActions";
import { useConversationsStore } from "@/stores/conversationsStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({ api: { chat: { deleteSession: vi.fn().mockResolvedValue({}) } } }));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

function setup({ params, currentSessionId = "b", sessions = [{ session_id: "b" }] }) {
	const chatStore = {
		removeSession: vi.fn(),
		currentSessionId,
		sessions,
		sortedSessions: sessions,
	};
	const router = { push: vi.fn() };
	const handleNewChat = vi.fn();
	const actions = useChatSessionActions({ chatStore, route: { params }, router, handleNewChat });
	return { ...actions, router, handleNewChat };
}

describe("handleDeleteSession", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
	});

	it("also removes an archived chat from the search results", async () => {
		const conversations = useConversationsStore();
		conversations.searchResults = [{ session_id: "a" }, { session_id: "b" }];
		const { handleDeleteSession } = setup({ params: { sessionId: "b" } });
		await handleDeleteSession("a");
		expect(api.chat.deleteSession).toHaveBeenCalledWith("a");
		expect(conversations.searchResults.map((s) => s.session_id)).toEqual(["b"]);
	});

	// currentSessionId outlives the chat route: it still names the last chat
	// opened after the user navigates to a project page or home.
	it("stays on the project page when archiving a chat from the sidebar", async () => {
		const { handleDeleteSession, router, handleNewChat } = setup({ params: { projectId: "p1" } });
		await handleDeleteSession("a");
		expect(router.push).not.toHaveBeenCalled();
		expect(handleNewChat).not.toHaveBeenCalled();
	});

	it("stays on home when archiving a chat from the sidebar", async () => {
		const { handleDeleteSession, router } = setup({ params: {} });
		await handleDeleteSession("a");
		expect(router.push).not.toHaveBeenCalled();
	});

	it("stays on the open chat when archiving a different one", async () => {
		const { handleDeleteSession, router } = setup({ params: { sessionId: "b" } });
		await handleDeleteSession("a");
		expect(router.push).not.toHaveBeenCalled();
	});

	it("opens the most recent chat when archiving the one on screen", async () => {
		const { handleDeleteSession, router } = setup({ params: { sessionId: "a" } });
		await handleDeleteSession("a");
		expect(router.push).toHaveBeenCalledWith("/chat/b");
	});

	it("starts a new chat when archiving the last one on screen", async () => {
		const { handleDeleteSession, router, handleNewChat } = setup({
			params: { sessionId: "a" },
			currentSessionId: null,
			sessions: [],
		});
		await handleDeleteSession("a");
		expect(router.push).not.toHaveBeenCalled();
		expect(handleNewChat).toHaveBeenCalledTimes(1);
	});
});
