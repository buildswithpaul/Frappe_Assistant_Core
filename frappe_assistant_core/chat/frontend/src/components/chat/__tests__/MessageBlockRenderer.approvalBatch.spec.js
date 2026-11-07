import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import MessageBlockRenderer from "@/components/chat/MessageBlockRenderer.vue";

const BatchStub = {
	name: "BatchedApprovalCard",
	props: ["blocks", "submitting"],
	template: `<div class="batch-stub" />`,
};

const InteractionCardStub = {
	name: "InteractionCard",
	props: ["block"],
	template: `<div class="interaction-stub" />`,
};

const ChangesStub = {
	name: "ChangesBlock",
	props: ["block", "messageId", "isStreaming"],
	template: `<div class="changes-stub" />`,
};

function mountRenderer(blocks, props = {}) {
	return mount(MessageBlockRenderer, {
		props: { blocks, messageIndex: 0, ...props },
		global: {
			stubs: {
				BatchedApprovalCard: BatchStub,
				InteractionCard: InteractionCardStub,
				ChangesBlock: ChangesStub,
				QuestionGroupCard: true,
				ProcessingCard: true,
				ProcessingIndicator: true,
				SourcesBlock: true,
				GeneratedDocumentsBlock: true,
				WorkflowCreatedBlock: true,
			},
		},
	});
}

const tool = (id) => ({ id, type: "tool_call", tool_name: "create_document", status: "running" });
const approval = (id, reason = { type: "approval", level: "R2" }, extra = {}) => ({
	id,
	type: "interaction",
	interactionType: reason.type,
	tool_name: "create_document",
	status: "pending",
	interrupts: [{ id: `i_${id}`, reason }],
	...extra,
});

describe("parallel approvals on one message", () => {
	it("two pending R2 approvals render one batched card", () => {
		const wrapper = mountRenderer([tool("a"), tool("b"), approval("a"), approval("b")]);
		const batches = wrapper.findAllComponents(BatchStub);
		expect(batches).toHaveLength(1);
		expect(batches[0].props("blocks").map((b) => b.id)).toEqual(["a", "b"]);
		expect(wrapper.findAllComponents(InteractionCardStub)).toHaveLength(0);
	});

	it("keeps an R3 approval on its own card, out of the batch", () => {
		const wrapper = mountRenderer([
			approval("a"),
			approval("b"),
			approval("c", { type: "approval", level: "R3" }),
		]);
		expect(wrapper.findAllComponents(BatchStub)[0].props("blocks").map((b) => b.id)).toEqual(["a", "b"]);
		expect(wrapper.findAllComponents(InteractionCardStub).map((c) => c.props("block").id)).toEqual(["c"]);
	});

	it("a build plan is never batched", () => {
		const plan = { type: "build_plan", level: "R2" };
		const wrapper = mountRenderer([approval("a", plan), approval("b", plan)]);
		expect(wrapper.findAllComponents(BatchStub)).toHaveLength(0);
		expect(wrapper.findAllComponents(InteractionCardStub)).toHaveLength(2);
	});

	// An approval with no level is not a leveled write (BYO tool, customisation, email): today's card.
	it("leaves unleveled approvals on their own cards", () => {
		const wrapper = mountRenderer([approval("a", { type: "approval" }), approval("b", { type: "approval" })]);
		expect(wrapper.findAllComponents(BatchStub)).toHaveLength(0);
		expect(wrapper.findAllComponents(InteractionCardStub)).toHaveLength(2);
	});

	it("leaves a lone R2 approval on its own card", () => {
		const wrapper = mountRenderer([approval("a")]);
		expect(wrapper.findAllComponents(BatchStub)).toHaveLength(0);
		expect(wrapper.findAllComponents(InteractionCardStub)).toHaveLength(1);
	});
});

describe("the changes list", () => {
	it("renders under the answer with the message id and stream state", () => {
		const changes = { type: "changes_made", id: "cm1", changes: [{ doctype: "Note", name: "N-1" }] };
		const text = { type: "text", id: "t1", content: "Done." };
		const wrapper = mountRenderer([changes, text], { messageId: "m1", isStreaming: true });

		const html = wrapper.html();
		expect(html.indexOf("changes-stub")).toBeGreaterThan(html.indexOf("Done."));
		const block = wrapper.findComponent(ChangesStub);
		expect(block.props("messageId")).toBe("m1");
		expect(block.props("isStreaming")).toBe(true);
	});
});
