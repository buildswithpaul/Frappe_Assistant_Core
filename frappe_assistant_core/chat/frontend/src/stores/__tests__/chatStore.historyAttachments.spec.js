import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { chat: { getMessages: vi.fn(), getLiveTurn: vi.fn() }, get: vi.fn() },
}));

// The shape FACChatMessage.get_session_messages returns: the files linked to
// the message ride along as `attachments`, one row per File doc.
const serverRows = () => [
	{
		role: "user",
		content: "Can you summarize this receipt?",
		attachments: [
			{
				name: "d5d4b1f079",
				file_name: "receipt.jpg",
				file_url: "/private/files/receipt.jpg",
				file_size: 6993,
			},
		],
	},
	{ role: "assistant", message_id: "m1", content: "Here is the summary.", attachments: [] },
];

describe("files on messages read back from the server", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
		vi.clearAllMocks();
		api.chat.getLiveTurn.mockResolvedValue(null);
	});

	it("shows the receipt on the user's message when the conversation is opened", async () => {
		api.chat.getMessages.mockResolvedValue({ messages: serverRows(), has_more: false });

		await store.loadMessages("s1");

		expect(store.messages[0].files).toEqual([{ name: "receipt.jpg", url: "/private/files/receipt.jpg" }]);
		expect(store.messages[1].files).toEqual([]);
	});

	it("keeps the receipt on the user's message after a reconnect re-reads history", async () => {
		store.currentSessionId = "s1";
		store.messages = [
			{ role: "user", content: "Can you summarize this receipt?", files: [{ name: "receipt.jpg", url: "/private/files/receipt.jpg" }] },
			{ role: "assistant", message_id: "m1", isStreaming: false, blocks: [] },
		];
		api.chat.getMessages.mockResolvedValue(serverRows());

		await store.reconcileFromServer("s1");

		expect(store.messages[0].files).toEqual([{ name: "receipt.jpg", url: "/private/files/receipt.jpg" }]);
	});
});
