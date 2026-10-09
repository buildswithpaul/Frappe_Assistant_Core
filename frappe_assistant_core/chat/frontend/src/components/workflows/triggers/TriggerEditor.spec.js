import { describe, it, expect, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

vi.mock("@/api/client", () => {
	const api = {
		workflows: {
			triggers: {
				list: vi.fn(),
				getDoctypeFields: vi.fn().mockResolvedValue({ fields: [] }),
				listDoctypes: vi.fn().mockResolvedValue({ doctypes: [] }),
			},
		},
	};
	return { api, default: api };
});

import TriggerEditor from "./TriggerEditor.vue";

const EXISTING = {
	name: "T1",
	title: "Big orders",
	reference_doctype: "Sales Order",
	doctype_event: "on_submit",
	changed_fields: "",
	enabled: 1,
	filters: [{ fieldname: "grand_total", operator: ">", value: "100000" }],
};

async function mountEditor(existing = EXISTING) {
	const w = mount(TriggerEditor, { props: { workflowName: "Digest", workflowId: "WF-1", existing } });
	await flushPromises();
	return w;
}

describe("TriggerEditor filters", () => {
	it("leaves filters out of the update when only the title changed", async () => {
		const w = await mountEditor();
		await w.get('[data-test="trigger-title"]').setValue("Big orders (EU)");
		await w.get('[data-test="trigger-save"]').trigger("click");
		const payload = w.emitted("save")[0][0];
		expect(payload.title).toBe("Big orders (EU)");
		expect("filters" in payload).toBe(false);
	});

	it("shows the saved filter rows without a second list call", async () => {
		const w = await mountEditor();
		expect(w.findAll(".filter-row")).toHaveLength(1);
	});

	it("sends filters when a row was removed", async () => {
		const w = await mountEditor();
		await w.get(".filter-row .icon-btn.danger").trigger("click");
		await w.get('[data-test="trigger-save"]').trigger("click");
		expect(JSON.parse(w.emitted("save")[0][0].filters)).toEqual([]);
	});

	it("always sends filters for a new trigger", async () => {
		const w = await mountEditor(null);
		await w.get('[data-test="trigger-title"]').setValue("New");
		w.vm.form.reference_doctype = "Sales Order";
		await w.vm.$nextTick();
		await w.get('[data-test="trigger-save"]').trigger("click");
		expect(w.emitted("save")[0][0].filters).toBe("[]");
	});
});

describe("TriggerEditor numeric filter values", () => {
	it("does not count a numeric saved value as a change", async () => {
		const w = await mountEditor({
			...EXISTING,
			filters: [{ fieldname: "grand_total", operator: ">", value: 100000 }],
		});
		// Typing the same digits back turns the loaded number into a string.
		await w.get(".filter-row input.field-input").setValue("100000");
		await w.get('[data-test="trigger-save"]').trigger("click");
		expect("filters" in w.emitted("save")[0][0]).toBe(false);
	});
});
