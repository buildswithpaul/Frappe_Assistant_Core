import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import BuilderNotices from "./BuilderNotices.vue";

describe("BuilderNotices problem list", () => {
	const errors = ['Task "a" is missing a system prompt', 'Task "b" is missing a system prompt'];

	it("counts the problems and keeps the list collapsed until asked", async () => {
		const wrapper = mount(BuilderNotices, { props: { validationErrors: errors } });
		expect(wrapper.text()).toContain("2 problems");
		expect(wrapper.find(".notice-list").exists()).toBe(false);

		const toggle = wrapper.find("button[aria-expanded]");
		expect(toggle.attributes("aria-expanded")).toBe("false");
		await toggle.trigger("click");
		expect(wrapper.findAll(".notice-list li").map((li) => li.text())).toEqual(errors);
	});
});
