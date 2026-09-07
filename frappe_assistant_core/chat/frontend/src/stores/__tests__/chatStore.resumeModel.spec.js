import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { useModelStore } from "@/stores/modelStore";
import { call } from "frappe-ui";

vi.mock("@/api/client", () => ({
	api: { chat: { send: vi.fn().mockResolvedValue({}) } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

/**
 * The model is turn state exactly like the composer toggles: a resume that
 * forwards nothing reaches AR as absence and the approved half of the turn
 * finishes on the tenant default instead of the model the user picked.
 *
 * The one thing that must never travel is the literal "auto" — a resume skips
 * classification, so "auto" would reach AR as a model id that doesn't exist.
 */
describe("chatStore.submitInterruptDecision — model", () => {
	let store;
	let models;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		models = useModelStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
	});

	function pauseOnAnApproval() {
		const paused = {
			role: "assistant",
			message_id: "m-1",
			blocks: [
				{
					type: "interaction",
					id: "call_1",
					status: "pending",
					interactionType: "approval",
					interrupts: [{ id: "int1" }],
				},
			],
		};
		store.messages = [paused];
		store.hasPendingInteraction = true;
		store.completeStreaming("partial", { interrupted: true, blocks: paused.blocks });
	}

	async function approve() {
		await store.submitInterruptDecision({
			blockId: "call_1",
			resolution: "approved",
			userResponse: null,
			response: "approve",
		});
		return call.mock.calls[0][1];
	}

	it("forwards an explicitly chosen model on resume", async () => {
		models.selectedModel = "claude-sonnet-4-6";
		pauseOnAnApproval();

		const payload = await approve();

		expect(payload.model_id).toBe("claude-sonnet-4-6");
	});

	it("never sends the literal auto — the resume path has no classifier", async () => {
		models.autoMode = { enabled: true };
		models.selectedModel = "auto";
		models.defaultModel = "claude-haiku-4-5";
		pauseOnAnApproval();

		const payload = await approve();

		expect(payload.model_id ?? null).toBeNull();
		expect(payload).not.toHaveProperty("model_id", "auto");
	});

	it("does not send auto when the tenant default is itself auto", async () => {
		// isAutoModeSelected only reads selectedModel, so a null selection with
		// an "auto" tenant default slips past a state-based guard.
		models.autoMode = { enabled: true };
		models.selectedModel = null;
		models.defaultModel = "auto";
		pauseOnAnApproval();

		const payload = await approve();

		expect(payload.model_id ?? null).toBeNull();
	});

	it("falls back to the tenant default when the user never picked, like send does", async () => {
		models.defaultModel = "claude-haiku-4-5";
		pauseOnAnApproval();

		const payload = await approve();

		expect(payload.model_id).toBe("claude-haiku-4-5");
	});

	it("still carries the composer toggles alongside the model", async () => {
		models.selectedModel = "claude-sonnet-4-6";
		pauseOnAnApproval();

		const payload = await approve();

		expect(payload).toMatchObject({
			session_id: "s1",
			web_search: false,
			thinking_enabled: false,
		});
	});
});
