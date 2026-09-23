import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import FeedbackForm from "./FeedbackForm.vue";

describe("FeedbackForm", () => {
	it("disables submit when both rating and comment are empty", () => {
		const wrapper = mount(FeedbackForm);
		expect(wrapper.find('button[type="submit"]').attributes("disabled")).toBeDefined();
	});

	it("enables submit with a comment and no rating", async () => {
		const wrapper = mount(FeedbackForm);
		await wrapper.find("textarea").setValue("The export button is hard to find");
		expect(wrapper.find('button[type="submit"]').attributes("disabled")).toBeUndefined();
	});

	it("emits a null rating when no star was picked", async () => {
		const wrapper = mount(FeedbackForm);
		await wrapper.find("textarea").setValue("A feature request");
		await wrapper.find("form").trigger("submit");
		expect(wrapper.emitted("submit")[0][0].rating).toBeNull();
	});

	it("still emits the rating when a star was picked", async () => {
		const wrapper = mount(FeedbackForm);
		await wrapper.findAll("button.star")[3].trigger("click");
		await wrapper.find("form").trigger("submit");
		expect(wrapper.emitted("submit")[0][0].rating).toBe(4);
	});
});
