import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import MessageBlockRenderer from "@/components/chat/MessageBlockRenderer.vue";

// #34546: an answer typed in the composer showed only as "Answered: ..." inside FACO's
// collapsed steps, never as something the user said.

function mountRenderer(blocks) {
	return mount(MessageBlockRenderer, {
		props: { blocks, messageIndex: 0, isStreaming: false },
		global: {
			stubs: {
				ProcessingCard: { props: ["blocks"], template: `<div class="card-stub">{{ blocks.length }}</div>` },
				InteractionCard: true,
				ProcessingIndicator: true,
			},
		},
	});
}

const tool = (id) => ({ id, type: "tool_call", tool_name: "dry_run_import", status: "success", input: {} });
const asked = (status, extra = {}) => ({
	id: "q1",
	type: "interaction",
	interactionType: "single_select",
	status,
	...extra,
});

describe("the user's answer to FACO's question", () => {
	it("shows as theirs where they gave it, and the steps after it start below", () => {
		const w = mountRenderer([tool("t1"), asked("answered", { userResponse: "Leave them out" }), tool("t2")]);

		const answer = w.find(".user-answer");
		expect(answer.exists()).toBe(true);
		expect(answer.text()).toContain("Leave them out");
		const html = w.html();
		const cards = w.findAll(".card-stub");
		expect(cards).toHaveLength(2);
		expect(html.indexOf("Leave them out")).toBeLessThan(html.lastIndexOf("card-stub"));
	});

	it("is not shown for an approval, nor for a question still waiting", () => {
		const approval = { ...asked("approved", { userResponse: "ok" }), interactionType: "approval" };
		expect(mountRenderer([tool("t1"), approval]).find(".user-answer").exists()).toBe(false);
		expect(mountRenderer([tool("t1"), asked("pending")]).find(".user-answer").exists()).toBe(false);
	});
});
