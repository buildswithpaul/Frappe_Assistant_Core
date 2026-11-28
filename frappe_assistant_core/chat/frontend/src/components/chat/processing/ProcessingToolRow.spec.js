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

describe("ProcessingToolRow summary", () => {
	// The shape AR streams for an MCP tool: content parts whose text is the tool's JSON.
	const listRow = (data, extra = {}) => ({
		id: "r1",
		status: "success",
		labelPrefix: "Listed records → ",
		target: "Customer",
		hasTarget: true,
		reason: "",
		appliesTo: null,
		block: {
			id: "r1",
			type: "tool_call",
			tool_name: "list_documents",
			status: "success",
			input: { doctype: "Customer" },
			result: [{ text: JSON.stringify({ success: true, data }) }],
			duration_ms: 1240,
			...extra,
		},
	});

	it("says how many records came back and how long the call took", () => {
		const wrapper = mount(ProcessingToolRow, { props: { row: listRow([{ name: "A" }, { name: "B" }]) } });
		expect(wrapper.find(".timeline-meta").text()).toBe("2 found · 1.2s");
	});

	it("says so when nothing was found", () => {
		expect(mount(ProcessingToolRow, { props: { row: listRow([]) } }).find(".timeline-meta").text()).toBe("none found · 1.2s");
	});

	it("says nothing of counts or time for a call that is still running or that failed", () => {
		// A running block has no result or duration yet; useActivityTimeline copies its status to the row.
		const running = listRow([], { status: "running", result: null, duration_ms: undefined });
		expect(mount(ProcessingToolRow, { props: { row: { ...running, status: "running" } } }).find(".timeline-meta").exists()).toBe(false);

		const failed = listRow([], { status: "error", result: [{ text: JSON.stringify({ success: false, error: "No permission" }) }] });
		expect(mount(ProcessingToolRow, { props: { row: { ...failed, status: "error" } } }).find(".timeline-meta").exists()).toBe(false);
	});

	it("says how many lookups a script made", () => {
		// A run_script block as the store holds it once its result, with the script's steps, has arrived.
		const block = {
			id: "s1",
			type: "tool_call",
			tool_name: "run_script",
			status: "success",
			input: { code: "print(1)" },
			result: [{ text: "1" }],
			duration_ms: 256,
			steps: [
				{ tool_name: "list_documents", input: { doctype: "Company" }, status: "success" },
				{ tool_name: "list_documents", input: { doctype: "Customer" }, status: "success" },
			],
		};
		const row = { id: "s1", status: "success", labelPrefix: "Ran a script", target: null, hasTarget: false, reason: "", appliesTo: null, block };

		expect(mount(ProcessingToolRow, { props: { row } }).find(".timeline-meta").text()).toBe("2 lookups · 256ms");
	});

	it("opens onto the call's summary", async () => {
		const wrapper = mount(ProcessingToolRow, { props: { row: listRow([{ name: "A" }]) } });
		await wrapper.find(".timeline-line").trigger("click");
		expect(wrapper.find(".tool-details th").text()).toBe("Name");
	});
});
