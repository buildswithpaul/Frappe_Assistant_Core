import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import TriggerCard from "./TriggerCard.vue";

const trigger = {
	name: "T1",
	title: "Big orders",
	enabled: 1,
	doctype_event: "on_submit",
	reference_doctype: "Sales Order",
	filters: [{ fieldname: "grand_total", operator: ">", value: "100000" }],
};

describe("TriggerCard", () => {
	it("shows the filter rows", () => {
		const w = mount(TriggerCard, { props: { trigger } });
		expect(w.text()).toContain("grand_total > 100000");
	});

	it("asks to test against a real document", async () => {
		const w = mount(TriggerCard, { props: { trigger } });
		await w.get('[data-test="trigger-test"]').trigger("click");
		expect(w.emitted("test")[0][0]).toEqual(trigger);
	});

	it("reports what the test found", () => {
		const w = mount(TriggerCard, {
			props: { trigger, testResult: { would_fire: false, sample_doc: "SO-0007", payload: { doc: {} } } },
		});
		expect(w.text()).toContain("SO-0007");
		expect(w.text()).toContain("would not fire");
	});

	it("renders filter values as text, never markup", () => {
		const evil = { ...trigger, filters: [{ fieldname: "title", operator: "=", value: "<b>x</b>" }] };
		const w = mount(TriggerCard, { props: { trigger: evil } });
		expect(w.find(".filter-chip b").exists()).toBe(false);
		expect(w.text()).toContain("<b>x</b>");
	});
});
