import { describe, it, expect } from "vitest";
import { ref } from "vue";
import { INTERNAL_TOOLS, createBlockHandlers } from "./blockHandlers";

describe("INTERNAL_TOOLS", () => {
	it("treats delegate as an internal orchestration tool", () => {
		expect(INTERNAL_TOOLS.has("delegate")).toBe(true);
	});
});

function makeHandlers(messagesArr) {
	return createBlockHandlers({
		messages: ref(messagesArr),
		isStreaming: ref(true),
		hasPendingInteraction: ref(false),
		activeThinkingBlockId: ref(null),
		activeToolCallId: ref(null),
		streamRequestId: ref("req-1"),
	});
}

describe("handleWorkflowCreatedEvent", () => {
	it("appends a workflow_created block to the streaming assistant message", () => {
		const msgs = [{ role: "assistant", isStreaming: true, blocks: [], _requestId: "req-1" }];
		const handlers = makeHandlers(msgs);
		handlers.handleWorkflowCreatedEvent({
			workflow_name: "A",
			docname: "WF-1",
			link: "/copilot/agents/WF-1",
			status: "Draft",
			action: "created",
		});
		const last = msgs[0].blocks[msgs[0].blocks.length - 1];
		expect(last).toMatchObject({
			type: "workflow_created",
			workflow_name: "A",
			docname: "WF-1",
			link: "/copilot/agents/WF-1",
			status: "Draft",
			action: "created",
		});
		expect(last.id).toBeTruthy();
	});

	it("ignores an event with no docname", () => {
		const msgs = [{ role: "assistant", isStreaming: true, blocks: [], _requestId: "req-1" }];
		makeHandlers(msgs).handleWorkflowCreatedEvent({ workflow_name: "X" });
		expect(msgs[0].blocks).toHaveLength(0);
	});
});

describe("getOrCreateStreamingMessage with a trailing queued bubble", () => {
	it("re-uses the streaming assistant message instead of spawning a phantom bubble", () => {
		const msgs = [
			{ role: "assistant", isStreaming: true, blocks: [], _requestId: "req-1" },
			{ role: "user", content: "queued text", queued: true, _queueId: "q1" },
		];
		const handlers = makeHandlers(msgs);
		handlers.handleWorkflowCreatedEvent({ workflow_name: "A", docname: "WF-1" });

		expect(msgs).toHaveLength(2);
		expect(msgs.filter((m) => m.role === "assistant")).toHaveLength(1);
		expect(msgs[0].blocks.some((b) => b.type === "workflow_created")).toBe(true);
	});
});

describe("recordInteractionDecision with don't-ask-again", () => {
	const card = (id, tool, extra = {}) => ({
		type: "interaction",
		id,
		interactionType: "approval",
		tool_name: tool,
		status: "pending",
		interrupts: [{ id: `i-${id}`, reason: { type: "approval", tool } }],
		...extra,
	});
	const turn = (...blocks) => [{ role: "assistant", isStreaming: true, _requestId: "req-1", blocks }];

	it("settles every pending card for the same tool", () => {
		const msgs = turn(card("a", "create_document"), card("b", "create_document"));
		const batch = makeHandlers(msgs).recordInteractionDecision("a", "trusted", "trust", "trust");
		expect(batch.responses).toEqual([
			{ interruptId: "i-a", response: "trust" },
			{ interruptId: "i-b", response: "trust" },
		]);
		expect(msgs[0].blocks[1].decision.resolution).toBe("trusted");
	});

	it("leaves cards for other tools waiting for their own answer", () => {
		const msgs = turn(card("a", "create_document"), card("c", "send_email"));
		const batch = makeHandlers(msgs).recordInteractionDecision("a", "trusted", "trust", "trust");
		expect(batch).toBeNull();
		expect(msgs[0].blocks[1].decision).toBeUndefined();
	});

	it("does not spread a one-time approval", () => {
		const msgs = turn(card("a", "create_document"), card("b", "create_document"));
		const batch = makeHandlers(msgs).recordInteractionDecision("a", "approved", "approve", "approve");
		expect(batch).toBeNull();
		expect(msgs[0].blocks[1].decision).toBeUndefined();
	});

	it("never settles a customisation card by trust given on another card", () => {
		const risky = (id, tool) =>
			card(id, tool, { interrupts: [{ id: `i-${id}`, reason: { type: "approval", risk: "customisation" } }] });
		const msgs = turn(card("a", "create_document"), risky("b", "create_document"), card("c", "create_document"));
		const handlers = makeHandlers(msgs);
		handlers.recordInteractionDecision("a", "trusted", "trust", "trust");
		expect(msgs[0].blocks[1].decision).toBeUndefined();
		expect(msgs[0].blocks[2].decision.resolution).toBe("trusted");
	});

	it("keeps a decision the user already made on another card", () => {
		const msgs = turn(card("a", "create_document"), card("b", "create_document"));
		const handlers = makeHandlers(msgs);
		handlers.recordInteractionDecision("b", "rejected", "rejected", "rejected");
		const batch = handlers.recordInteractionDecision("a", "trusted", "trust", "trust");
		expect(batch.responses).toEqual([
			{ interruptId: "i-a", response: "trust" },
			{ interruptId: "i-b", response: "rejected" },
		]);
	});
});
