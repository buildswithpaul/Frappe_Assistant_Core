import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import TriggerTestResult from "./TriggerTestResult.vue";

const base = { would_fire: false, sample_doc: "SO-1", payload: { doc: { name: "SO-1" } } };

describe("TriggerTestResult", () => {
	it("names the filter that failed, as text", () => {
		const w = mount(TriggerTestResult, {
			props: { result: { ...base, failed_filter: { fieldname: "status", operator: "=", value: "<i>x</i>" } } },
		});
		expect(w.get('[data-test="failed-filter"]').text()).toContain("status = <i>x</i>");
		expect(w.find("i").exists()).toBe(false);
	});

	it("omits the failed-filter line when none is named", () => {
		const w = mount(TriggerTestResult, { props: { result: { ...base, failed_filter: null } } });
		expect(w.find('[data-test="failed-filter"]').exists()).toBe(false);
		expect(w.text()).toContain("filters only");
	});

	it("shows the server message when there is no document", () => {
		const w = mount(TriggerTestResult, { props: { result: { payload: null, message: "No documents of type X found." } } });
		expect(w.text()).toContain("No documents of type X found.");
	});

	it("shows the testing state", () => {
		const w = mount(TriggerTestResult, { props: { testing: true } });
		expect(w.text()).toContain("Testing against the latest document");
	});

	it("renders the payload only once the details are opened", async () => {
		const w = mount(TriggerTestResult, { props: { result: { ...base, would_fire: true } } });
		expect(w.find("pre").exists()).toBe(false);
		const d = w.get("details");
		d.element.open = true;
		await d.trigger("toggle");
		expect(w.get("pre").text()).toContain("SO-1");
	});
});
