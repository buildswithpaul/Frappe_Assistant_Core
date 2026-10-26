import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { defineComponent, h } from "vue";

import InputArea from "../InputArea.vue";
import InteractionCard from "../InteractionCard.vue";
import { planBlock } from "../interactions/buildPlan.testdata";

// The card and the composer sit far apart in the real tree, as they do in ChatView and WidgetPanel.
const Page = defineComponent({
	props: { block: { type: Object, required: true } },
	setup: (props) => () => h("div", [h(InteractionCard, { block: props.block }), h(InputArea)]),
});

describe("InteractionCard with a build plan", () => {
	let wrapper;
	beforeEach(() => setActivePinia(createPinia()));
	afterEach(() => {
		wrapper?.unmount();
		document.body.innerHTML = "";
	});

	it("draws the plan card, not a question card", () => {
		wrapper = mount(InteractionCard, { props: { block: planBlock() } });
		expect(wrapper.findComponent({ name: "BuildPlanCard" }).exists()).toBe(true);
		expect(wrapper.findComponent({ name: "QuestionCard" }).exists()).toBe(false);
	});

	it("passes the plan approval up unchanged", async () => {
		const block = planBlock();
		wrapper = mount(InteractionCard, { props: { block } });
		await wrapper.find(".ix-actions .ql-btn-approve").trigger("click");
		const [, responses] = wrapper.emitted("approve")[0];
		expect(responses[0].response).toEqual({ decision: "approve", plan_id: block.interrupts[0].reason.plan_id });
	});

	it("Ask for changes puts the cursor in the composer", async () => {
		wrapper = mount(Page, { props: { block: planBlock() }, attachTo: document.body });
		await wrapper.find(".ix-actions .ql-btn-reject").trigger("click");
		await wrapper.vm.$nextTick();
		expect(document.activeElement).toBe(wrapper.find("textarea.input-textarea").element);
	});

	it("shows Plan approved once resolved", () => {
		wrapper = mount(InteractionCard, { props: { block: { ...planBlock(), status: "approved" } } });
		expect(wrapper.text()).toContain("Plan approved");
	});
});
