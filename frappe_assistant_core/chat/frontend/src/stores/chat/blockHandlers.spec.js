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
		autoModeSelection: ref(null),
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
