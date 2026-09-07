import { mount, flushPromises } from "@vue/test-utils";
import { describe, it, expect } from "vitest";

import QuestionCard from "@/components/chat/interactions/QuestionCard.vue";

const singleSelectBlock = {
	question: 'Which dates did you mean by "25-26"?',
	options: [
		"December 25-26, 2025",
		"A specific month (25th-26th) — please specify which month",
		"Something else — I'll type the exact dates",
	],
};

function mountSingleSelect(block = singleSelectBlock) {
	return mount(QuestionCard, {
		props: { block, interactionType: "single_select" },
	});
}

describe("QuestionCard single_select", () => {
	it("emits the option label when a canned pill is clicked", async () => {
		const wrapper = mountSingleSelect();
		// The first three pills are the canned options.
		const pills = wrapper.findAll(".pill");
		await pills[0].trigger("click");
		expect(wrapper.emitted("respond")[0]).toEqual(["December 25-26, 2025"]);
	});

	it("renders a 'Type a different answer' free-text escape hatch", () => {
		const wrapper = mountSingleSelect();
		const labels = wrapper.findAll(".pill").map((p) => p.text());
		expect(labels).toContain("Type a different answer");
	});

	it("hides the free-text input until the escape hatch is clicked", () => {
		const wrapper = mountSingleSelect();
		expect(wrapper.find(".custom-input-row").exists()).toBe(false);
	});

	it("reveals a text input when the escape hatch is clicked", async () => {
		const wrapper = mountSingleSelect();
		const custom = wrapper.find(".pill-custom");
		await custom.trigger("click");
		await flushPromises();
		expect(wrapper.find(".custom-input-row").exists()).toBe(true);
		expect(wrapper.find(".custom-input-row input").exists()).toBe(true);
	});

	it("emits the typed answer (not an option label) when the user types and sends", async () => {
		const wrapper = mountSingleSelect();
		await wrapper.find(".pill-custom").trigger("click");
		await flushPromises();
		const input = wrapper.find(".custom-input-row input");
		await input.setValue("July 25-26, 2025");
		await wrapper.find(".custom-input-row button").trigger("click");
		expect(wrapper.emitted("respond").at(-1)).toEqual(["July 25-26, 2025"]);
	});

	it("does not emit an empty/whitespace custom answer", async () => {
		const wrapper = mountSingleSelect();
		await wrapper.find(".pill-custom").trigger("click");
		await flushPromises();
		const input = wrapper.find(".custom-input-row input");
		await input.setValue("   ");
		// Send button is disabled for whitespace-only input.
		expect(wrapper.find(".custom-input-row button").attributes("disabled")).toBeDefined();
	});
});
