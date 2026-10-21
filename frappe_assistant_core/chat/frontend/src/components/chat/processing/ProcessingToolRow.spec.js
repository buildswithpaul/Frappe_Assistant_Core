import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ProcessingToolRow from "./ProcessingToolRow.vue";

const row = (appliesTo) => ({
	id: "w1",
	status: "success",
	labelPrefix: "Created Custom Field → ",
	target: "Customer-po",
	hasTarget: true,
	reason: "",
	appliesTo,
	block: { id: "w1", type: "tool_call", tool_name: "create_document", status: "success", input: {}, result: {} },
});

describe("ProcessingToolRow open link", () => {
	it("links to a new form of the doctype the change applies to", () => {
		const link = mount(ProcessingToolRow, { props: { row: row({ doctype: "Customer", url: "/desk/customer/new" }) } }).find("a.timeline-open");
		expect(link.text()).toBe("Open a new Customer");
		expect(link.attributes("href")).toBe("/desk/customer/new");
		expect(link.attributes("target")).toBe("_blank");
		expect(link.attributes("rel")).toBe("noopener");
	});

	it("has no link without applies_to", () => {
		expect(mount(ProcessingToolRow, { props: { row: row(null) } }).find("a.timeline-open").exists()).toBe(false);
	});
});
