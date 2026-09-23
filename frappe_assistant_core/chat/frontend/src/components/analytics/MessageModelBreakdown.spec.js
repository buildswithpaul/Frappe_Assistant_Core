import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";
import MessageModelBreakdown from "./MessageModelBreakdown.vue";

const BREAKDOWN = [
	{
		model_id: "claude-sonnet-4-6",
		role: "orchestrator",
		credits: 180,
		input_tokens: 4200,
		output_tokens: 1100,
	},
	{
		model_id: "claude-haiku-4-5-20251001",
		role: "helper",
		credits: 80,
		input_tokens: 9000,
		output_tokens: 2400,
	},
];

describe("MessageModelBreakdown", () => {
	it("renders one row per model with role classes", () => {
		const wrapper = mount(MessageModelBreakdown, { props: { breakdown: BREAKDOWN } });
		const rows = wrapper.findAll(".breakdown-row");
		expect(rows).toHaveLength(2);
		expect(wrapper.find(".bd-role.orchestrator").exists()).toBe(true);
		expect(wrapper.find(".bd-role.helper").exists()).toBe(true);
	});

	it("shows each model's own credits", () => {
		const wrapper = mount(MessageModelBreakdown, { props: { breakdown: BREAKDOWN } });
		const text = wrapper.text();
		expect(text).toContain("180 cr");
		expect(text).toContain("80 cr");
	});

	it("strips the date suffix from the model id", () => {
		const wrapper = mount(MessageModelBreakdown, { props: { breakdown: BREAKDOWN } });
		expect(wrapper.text()).toContain("claude-haiku-4-5");
		expect(wrapper.text()).not.toContain("20251001");
	});

	it("does not expose raw token counts (everything is credits)", () => {
		const wrapper = mount(MessageModelBreakdown, { props: { breakdown: BREAKDOWN } });
		expect(wrapper.text()).not.toContain("tok");
		expect(wrapper.text()).not.toContain("4,200");
		expect(wrapper.text()).not.toContain("5,300");
	});

	it("renders nothing meaningful for an empty breakdown", () => {
		const wrapper = mount(MessageModelBreakdown, { props: { breakdown: [] } });
		expect(wrapper.findAll(".breakdown-row")).toHaveLength(0);
	});
});
