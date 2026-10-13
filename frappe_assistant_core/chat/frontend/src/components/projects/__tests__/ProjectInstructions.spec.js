import { describe, it, expect, beforeAll, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import ProjectInstructions from "@/components/projects/ProjectInstructions.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

const mountIt = (saveFn = vi.fn().mockResolvedValue()) =>
	mount(ProjectInstructions, { props: { modelValue: "Amounts in INR.", saveFn } });

describe("ProjectInstructions", () => {
	it("shows the text read-only", () => {
		const w = mountIt();
		expect(w.text()).toContain("Amounts in INR.");
		expect(w.find("textarea").exists()).toBe(false);
	});

	it("shows the empty hint when there are no instructions", () => {
		const w = mount(ProjectInstructions, { props: { modelValue: "", saveFn: vi.fn() } });
		expect(w.text()).toContain("No instructions yet");
	});

	it("disables save over the limit and shows the counter", async () => {
		const w = mountIt();
		await w.find("[data-test=edit-instructions]").trigger("click");
		await w.find("textarea").setValue("x".repeat(8001));
		expect(w.find("[data-test=save-instructions]").attributes("disabled")).toBeDefined();
		expect(w.text()).toContain("8001 / 8000");
	});

	it("saves the draft and closes once the update resolves", async () => {
		const saveFn = vi.fn().mockResolvedValue();
		const w = mountIt(saveFn);
		await w.find("[data-test=edit-instructions]").trigger("click");
		await w.find("textarea").setValue("New");
		await w.find("[data-test=save-instructions]").trigger("click");
		await flushPromises();
		expect(saveFn).toHaveBeenCalledWith("New");
		expect(w.find("textarea").exists()).toBe(false);
	});

	it("a failing save keeps the editor open with the draft", async () => {
		const saveFn = vi.fn().mockRejectedValue(new Error("boom"));
		const w = mountIt(saveFn);
		await w.find("[data-test=edit-instructions]").trigger("click");
		await w.find("textarea").setValue("precious draft");
		await w.find("[data-test=save-instructions]").trigger("click");
		await flushPromises();
		expect(w.find("textarea").element.value).toBe("precious draft");
		expect(w.find("[data-test=save-instructions]").attributes("disabled")).toBeUndefined();
	});

	it("unchanged text closes without saving", async () => {
		const saveFn = vi.fn();
		const w = mountIt(saveFn);
		await w.find("[data-test=edit-instructions]").trigger("click");
		await w.find("[data-test=save-instructions]").trigger("click");
		expect(saveFn).not.toHaveBeenCalled();
		expect(w.find("textarea").exists()).toBe(false);
	});

	it("cancel discards the draft without saving", async () => {
		const w = mountIt();
		await w.find("[data-test=edit-instructions]").trigger("click");
		await w.find("textarea").setValue("changed");
		await w.find("[data-test=cancel-instructions]").trigger("click");
		expect(w.props("saveFn")).not.toHaveBeenCalled();
		expect(w.text()).toContain("Amounts in INR.");
	});
});
