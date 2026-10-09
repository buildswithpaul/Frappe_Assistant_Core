import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

const searchLink = vi.fn().mockResolvedValue([{ value: "Northwind Ltd", description: "" }]);
vi.mock("@/api/client", () => {
	const api = { workflows: { searchLink: (...a) => searchLink(...a) } };
	return { api, default: api };
});

import TemplateImportStep from "./TemplateImportStep.vue";
import LinkPicker from "./triggers/LinkPicker.vue";

const template = {
	template_name: "Weekly Collections Brief",
	variables_schema: {
		company: { type: "link", options: "Company", label: "Company", required: true },
		aging_days: { type: "int", label: "Aging threshold (days)", default: 30 },
	},
};

describe("TemplateImportStep", () => {
	it("does not import while a required field is empty, and says which", async () => {
		const w = mount(TemplateImportStep, { props: { template } });
		await w.get('[data-test="import-submit"]').trigger("click");
		expect(w.emitted("import")).toBeUndefined();
		expect(w.text()).toContain("Company is required");
	});

	it("uses a link picker that searches the doctype on this site", async () => {
		const w = mount(TemplateImportStep, { props: { template } });
		const picker = w.findComponent(LinkPicker);
		expect(picker.exists()).toBe(true);
		const result = await picker.props("fetcher")("North");
		expect(searchLink).toHaveBeenCalledWith("Company", "North");
		expect(result.options[0].value).toBe("Northwind Ltd");
	});

	it("imports typed values", async () => {
		const w = mount(TemplateImportStep, { props: { template } });
		w.findComponent(LinkPicker).vm.$emit("update:modelValue", "Northwind Ltd");
		await w.get('[data-test="import-submit"]').trigger("click");
		expect(w.emitted("import")[0][0]).toEqual({
			name: "Weekly Collections Brief",
			variables: { company: "Northwind Ltd", aging_days: 30 },
		});
	});

	it("opens a template whose schema is not valid JSON", () => {
		const w = mount(TemplateImportStep, {
			props: { template: { template_name: "Broken", variables_schema: "{oops", default_variables: "{nope" } },
		});
		expect(w.text()).toContain("Broken");
		expect(w.find('[data-test="import-submit"]').exists()).toBe(true);
	});

	it("never sends a sample link or email default from the template", async () => {
		const w = mount(TemplateImportStep, {
			props: {
				template: {
					template_name: "Sample",
					variables_schema: {
						company: { type: "link", options: "Company" },
						notify: { type: "email" },
					},
					default_variables: { company: "Your Company", notify: "you@example.com" },
				},
			},
		});
		await w.get('[data-test="import-submit"]').trigger("click");
		expect(w.emitted("import")[0][0].variables).toBe(null);
	});

	it("shows the field label rather than using the description as a placeholder", () => {
		const w = mount(TemplateImportStep, {
			props: {
				template: {
					template_name: "T",
					variables_schema: { notes: { type: "text", label: "Notes", description: "Anything the team should know" } },
				},
			},
		});
		expect(w.text()).toContain("Notes");
		expect(w.get("input.var-input").attributes("placeholder")).toBeUndefined();
	});
});
