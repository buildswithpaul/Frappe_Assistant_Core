import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { nextTick } from "vue";
import { useChatStore } from "@/stores/chatStore";
import { useUserStore } from "@/stores/userStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: {
		chat: { getSessions: vi.fn() },
		feedback: { answerRatings: vi.fn().mockResolvedValue({}) },
	},
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

describe("chatStore answer ratings", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
		// production: the capabilities endpoint passes through AR's feedback_v2 block.
		useUserStore().capabilities = { feedback_v2: true };
	});

	it("loads the ratings of the session that becomes current", async () => {
		const store = useChatStore();
		// production: loadMessages(sessionId) assigns currentSessionId when a conversation opens.
		store.currentSessionId = "s9";
		await nextTick();
		expect(api.feedback.answerRatings).toHaveBeenCalledWith("s9");
	});
});
