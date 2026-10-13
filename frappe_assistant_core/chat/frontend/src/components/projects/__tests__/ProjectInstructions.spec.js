import { describe, it, expect, beforeAll } from "vitest";
import { mount } from "@vue/test-utils";
import ProjectInstructions from "@/components/projects/ProjectInstructions.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

const mountIt = () => mount(ProjectInstructions, { props: { modelValue: "Amounts in INR." } });

describe("ProjectInstructions", () => {
	it("shows the text read-only", () => {
		const w = mountIt();
		expect(w.text()).toContain("Amounts in INR.");
		expect(w.find("textarea").exists()).toBe(false);
	});

	it("shows the empty hint when there are no instructions", () => {
		const w = mount(ProjectInstructions, { props: { modelValue: "" } });
		expect(w.text()).toContain("No instructions yet");
	});

	it("disables save over the limit and shows the counter", async () => {
		const w = mountIt();
		await w.find("[data-test=edit-instructions]").trigger("click");
		await w.find("textarea").setValue("x".repeat(8001));
		expect(w.find("[data-test=save-instructions]").attributes("disabled")).toBeDefined();
		expect(w.text()).toContain("8001 / 8000");
	});

	it("emits save with the draft", async () => {
		const w = mountIt();
		await w.find("[data-test=edit-instructions]").trigger("click");
		await w.find("textarea").setValue("New");
		await w.find("[data-test=save-instructions]").trigger("click");
		expect(w.emitted("save")[0]).toEqual(["New"]);
		expect(w.find("textarea").exists()).toBe(false);
	});

	it("cancel emits nothing", async () => {
		const w = mountIt();
		await w.find("[data-test=edit-instructions]").trigger("click");
		await w.find("textarea").setValue("changed");
		await w.find("[data-test=cancel-instructions]").trigger("click");
		expect(w.emitted("save")).toBeUndefined();
		expect(w.text()).toContain("Amounts in INR.");
	});
});
