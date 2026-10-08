import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useChatStore } from "@/stores/chatStore";
import { call } from "frappe-ui";

vi.mock("@/api/client", () => ({ api: { chat: { getMessages: vi.fn(), getLiveTurn: vi.fn() } } }));
vi.mock("frappe-ui", () => ({ call: vi.fn().mockResolvedValue({}) }));

const card = () => ({
	type: "interaction",
	id: "call_1",
	status: "pending",
	interactionType: "approval",
	interrupts: [{ id: "int1" }],
});

/**
 * Live round 3 (B3): after a rebuild the decided card can sit on a bubble that
 * has no message_id (applyLiveSnapshot pushes one when the snapshot carries
 * none), while the paused row from history holds the same card with its id.
 * The resume went out with message_id null and AR minted a new row.
 */
describe("the resume names the paused row", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		store = useChatStore();
		store.currentSessionId = "s1";
		vi.clearAllMocks();
	});

	const approve = () =>
		store.submitInterruptDecision({ blockId: "call_1", resolution: "approved", userResponse: null, response: "approve" });

	it("takes the id of the row that holds the decided card", async () => {
		store.messages = [
			{ role: "user", content: "create it" },
			{ role: "assistant", message_id: "m-1", content: "partial", blocks: [card()] },
			{ role: "assistant", content: "", blocks: [card()] },
		];

		await approve();

		expect(call.mock.calls[0][1].message_id).toBe("m-1");
	});

	it("leaves it to the server when no row holding the card has an id", async () => {
		store.messages = [
			{ role: "assistant", message_id: "m-0", content: "an earlier answer", blocks: [] },
			{ role: "assistant", content: "", blocks: [card()] },
		];

		await approve();

		expect(call.mock.calls[0][1].message_id).toBeNull();
	});
});
