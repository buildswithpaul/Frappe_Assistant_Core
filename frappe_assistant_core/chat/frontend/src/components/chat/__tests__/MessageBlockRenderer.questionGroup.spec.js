import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import MessageBlockRenderer from "@/components/chat/MessageBlockRenderer.vue";

// Redmine #34474: parallel ask_user calls render one card each; together they must read as
// one card with progress, so a pick is visible and nothing sends before the last answer.

const QuestionGroupStub = {
	name: "QuestionGroupCard",
	props: ["blocks", "submitting"],
	template: `<div class="group-stub" />`,
};

const InteractionCardStub = {
	name: "InteractionCard",
	props: ["block"],
	template: `<div class="interaction-stub" />`,
};

function mountRenderer(blocks, isResuming = false) {
	return mount(MessageBlockRenderer, {
		props: { blocks, messageIndex: 0, isResuming },
		global: {
			stubs: {
				QuestionGroupCard: QuestionGroupStub,
				InteractionCard: InteractionCardStub,
				ProcessingCard: true,
				ProcessingIndicator: true,
				SourcesBlock: true,
				GeneratedDocumentsBlock: true,
				WorkflowCreatedBlock: true,
			},
		},
	});
}

const askTool = (id) => ({ id: `t_${id}`, type: "tool_call", tool_name: "ask_user", status: "running" });
const question = (id, status = "pending") => ({
	id,
	type: "interaction",
	interactionType: "single_select",
	status,
	question: `Question ${id}?`,
	options: ["A", "B"],
	interrupts: [{ id: `i_${id}` }],
});

describe("questions FACO asks together", () => {
	it("render as one group card, in the order they were asked", () => {
		const wrapper = mountRenderer([askTool("q1"), askTool("q2"), question("q1"), question("q2")], true);

		const groups = wrapper.findAllComponents(QuestionGroupStub);
		expect(groups).toHaveLength(1);
		expect(groups[0].props("blocks").map((b) => b.id)).toEqual(["q1", "q2"]);
		expect(groups[0].props("submitting")).toBe(true);
		expect(wrapper.findAllComponents(InteractionCardStub)).toHaveLength(0);
	});

	it("leave a single question on its own card", () => {
		const wrapper = mountRenderer([askTool("q1"), question("q1")]);
		expect(wrapper.findAllComponents(QuestionGroupStub)).toHaveLength(0);
		expect(wrapper.findAllComponents(InteractionCardStub)).toHaveLength(1);
	});

	it("stay one card as a record once answered", () => {
		const wrapper = mountRenderer([question("q1", "answered"), question("q2", "answered")]);
		expect(wrapper.findAllComponents(QuestionGroupStub)).toHaveLength(1);
	});
});
