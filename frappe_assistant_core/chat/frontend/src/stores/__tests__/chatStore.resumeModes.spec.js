import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { useComposerModesStore } from "@/stores/composerModesStore";
import { call } from "frappe-ui";

vi.mock("@/api/client", () => ({
	api: { chat: { send: vi.fn().mockResolvedValue({}) } },
}));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

/**
 * A HITL resume continues the very turn the user approved, so it has to run
 * under that turn's composer toggles.
 *
 * Absence is a value the SPA never chooses: composerModesStore defaults
 * webSearch:false and always sends it explicitly. A resume that forwards
 * nothing therefore reaches AR as absence — and AR reads absence as "search
 * available", so every approval silently re-enabled web search against the
 * state the pill was showing, potentially egressing agent-composed text to a
 * search provider on a turn the user marked search-off.
 */
describe("chatStore.submitInterruptDecision — composer modes", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
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

	it("forwards the conversation's toggles on resume", async () => {
		const modes = useComposerModesStore();
		modes.toggle("s1", "thinking");
		pauseOnAnApproval();

		const payload = await approve();

		expect(payload.web_search).toBe(false);
		expect(payload.thinking_enabled).toBe(true);
	});

	it("never lets an approval re-enable a search the user switched off", async () => {
		// webSearch defaults false and stays false — the explicit off must be on
		// the wire, not merely absent from it.
		pauseOnAnApproval();

		const payload = await approve();

		expect(payload).toHaveProperty("web_search", false);
		expect(payload).toHaveProperty("thinking_enabled", false);
	});

	it("reads the modes of the session being resumed, not another conversation's", async () => {
		const modes = useComposerModesStore();
		modes.toggle("other-session", "webSearch");
		pauseOnAnApproval();

		const payload = await approve();

		expect(payload.session_id).toBe("s1");
		expect(payload.web_search).toBe(false);
	});
});
