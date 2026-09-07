import { describe, it, expect } from "vitest";
import { ref } from "vue";
import { createBlockHandlers } from "./blockHandlers";

function setup(messagesValue) {
	const messages = ref(messagesValue);
	const hasPendingInteraction = ref(true);
	return {
		messages,
		hasPendingInteraction,
		handlers: createBlockHandlers({
			messages,
			isStreaming: ref(true),
			hasPendingInteraction,
			activeThinkingBlockId: ref(null),
			activeToolCallId: ref(null),
			autoModeSelection: ref(null),
			streamRequestId: ref("req-1"),
		}),
	};
}

const twoPendingCards = () => [
	{
		role: "assistant",
		blocks: [
			{ type: "interaction", id: "tool-a", status: "pending" },
			{ type: "interaction", id: "tool-b", status: "pending" },
		],
	},
];

describe("session-wide interrupt lifecycle", () => {
	it("expires every pending card in the session, not just the newest", () => {
		const { messages, handlers } = setup(twoPendingCards());
		expect(handlers.markInterruptExpired()).toBe(true);
		const statuses = messages.value[0].blocks.map((b) => b.status);
		expect(statuses).toEqual(["expired", "expired"]);
	});

	it("dismisses every pending card when the pause resolves elsewhere", () => {
		const { messages, handlers } = setup(twoPendingCards());
		expect(handlers.dismissResolvedInterrupt()).toBe(true);
		const statuses = messages.value[0].blocks.map((b) => b.status);
		expect(statuses).toEqual(["resolved_elsewhere", "resolved_elsewhere"]);
	});

	it("flips pending cards across separate assistant messages", () => {
		const { messages, handlers } = setup([
			{ role: "assistant", blocks: [{ type: "interaction", id: "tool-a", status: "pending" }] },
			{ role: "user", content: "still waiting?" },
			{ role: "assistant", blocks: [{ type: "interaction", id: "tool-b", status: "pending" }] },
		]);
		expect(handlers.markInterruptExpired()).toBe(true);
		expect(messages.value[0].blocks[0].status).toBe("expired");
		expect(messages.value[2].blocks[0].status).toBe("expired");
	});

	it("leaves already-resolved cards untouched", () => {
		const { messages, handlers } = setup([
			{
				role: "assistant",
				blocks: [
					{ type: "interaction", id: "tool-a", status: "approved" },
					{ type: "interaction", id: "tool-b", status: "pending" },
				],
			},
		]);
		handlers.markInterruptExpired();
		expect(messages.value[0].blocks.map((b) => b.status)).toEqual(["approved", "expired"]);
	});

	it("unlocks the composer once the pending cards are flipped", () => {
		const { hasPendingInteraction, handlers } = setup(twoPendingCards());
		handlers.markInterruptExpired();
		expect(hasPendingInteraction.value).toBe(false);
	});

	it("reports false when there is nothing pending", () => {
		const { hasPendingInteraction, handlers } = setup([
			{ role: "assistant", blocks: [{ type: "text", content: "hi" }] },
		]);
		expect(handlers.markInterruptExpired()).toBe(false);
		expect(hasPendingInteraction.value).toBe(true);
	});
});
