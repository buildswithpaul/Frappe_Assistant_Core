import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
	api: { chat: { getMessages: vi.fn(), cancelStream: vi.fn().mockResolvedValue({}) } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

// "text_input" is the REAL value ask_user cards persist with — there is no
// "question" value anywhere in the system. See InteractionCard.vue: approval
// is the one special interactionType (and the default when absent); every
// other value, including this one, renders QuestionCard.
function interaction(overrides = {}) {
	return {
		type: "interaction",
		id: "blk1",
		status: "pending",
		interactionType: "text_input",
		interrupts: [{ id: "int1" }],
		...overrides,
	};
}

describe("pendingInteractionBlock", () => {
	let store;
	beforeEach(() => {
		setActivePinia(createPinia());
		store = useChatStore();
		vi.clearAllMocks();
	});

	it("classifies a real ask_user card (interactionType: text_input) as question regime", () => {
		// Regression pin: fb73e70 classified against an invented "question"
		// value that no real card ever sends, which left the composer
		// aborting every live question card instead of answering it.
		store.messages = [
			{ role: "user", content: "hi" },
			{ role: "assistant", blocks: [interaction()] },
		];
		expect(store.pendingInteractionBlock.regime).toBe("question");
		expect(store.pendingInteractionBlock.block.id).toBe("blk1");
	});

	it("classifies an unknown/future interactionType as question regime", () => {
		// Only "approval" is special; every other value — present or future —
		// must fall through to the question regime, not the reverse.
		store.messages = [
			{
				role: "assistant",
				blocks: [interaction({ interactionType: "some_future_type" })],
			},
		];
		expect(store.pendingInteractionBlock.regime).toBe("question");
	});

	it("is null when every interaction is resolved", () => {
		store.messages = [
			{ role: "assistant", blocks: [interaction({ status: "answered" })] },
		];
		expect(store.pendingInteractionBlock).toBeNull();
	});

	it("treats a mixed pending set as approval regime", () => {
		store.messages = [
			{
				role: "assistant",
				blocks: [
					interaction({ id: "q1", interactionType: "text_input" }),
					interaction({ id: "a1", interactionType: "approval" }),
				],
			},
		];
		expect(store.pendingInteractionBlock.regime).toBe("approval");
	});

	it("defaults missing interactionType to approval", () => {
		store.messages = [
			{ role: "assistant", blocks: [interaction({ interactionType: undefined })] },
		];
		expect(store.pendingInteractionBlock.regime).toBe("approval");
	});

	it("answerPendingQuestion sends the composer text as the card's resume payload", async () => {
		// Assert at the WIRE seam, not on a store-method spy: Pinia setup
		// stores call their own functions by local reference, so
		// vi.spyOn(store, ...) never intercepts an internal call.
		const { call } = await import("frappe-ui");
		store.currentSessionId = "s1";
		store.messages = [
			{ role: "assistant", message_id: "m1", blocks: [interaction()] },
		];

		await store.answerPendingQuestion("Tony Stark");

		expect(call).toHaveBeenCalledWith(
			"frappe_assistant_core.chat.api.chat.resume_interrupt",
			expect.objectContaining({
				session_id: "s1",
				interrupt_response: JSON.stringify([
					{ interruptId: "int1", response: "Tony Stark" },
				]),
			})
		);
	});

	it("abortPendingInteraction calls cancelStream for the current session", async () => {
		store.currentSessionId = "s1";
		await store.abortPendingInteraction();
		expect(api.chat.cancelStream).toHaveBeenCalledWith("s1", null);
	});
});
