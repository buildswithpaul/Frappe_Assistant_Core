import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";
import ToolDetails from "./ToolDetails.vue";

// The shape AR streams and FAC stores for an MCP tool: content parts whose text is the tool's JSON.
const parts = (value) => [{ text: typeof value === "string" ? value : JSON.stringify(value) }];
const customers = Array.from({ length: 8 }, (_, i) => ({ name: `CUST-${i + 1}`, territory: "North" }));
const LIST = {
	id: "t1",
	type: "tool_call",
	tool_name: "list_documents",
	status: "success",
	input: { doctype: "Customer", filters: { territory: "North" }, limit: 8 },
	result: parts({ success: true, data: customers, total_count: 8 }),
};
const SCRIPT = {
	id: "t2",
	type: "tool_call",
	tool_name: "run_script",
	status: "success",
	input: { code: 'c = await list_documents(doctype="Customer", limit=2)\nprint(c["data"])' },
	result: parts("[{'name': 'CUST-1', 'territory': 'North'}, {'name': 'CUST-2', 'territory': None}]"),
};

const tab = (wrapper, label) => wrapper.findAll(".details-tab").find((button) => button.text() === label);

describe("ToolDetails", () => {
	beforeEach(() => window.localStorage.clear());

	it("opens an ordinary call on what was asked for and a table of what came back", async () => {
		const wrapper = mount(ToolDetails, { props: { block: LIST } });

		expect(wrapper.findAll(".summary-pills li").map((pill) => pill.text())).toEqual(["Territory is North", "Up to 8"]);
		expect(wrapper.findAll("th").map((th) => th.text())).toEqual(["Name", "Territory"]);
		expect(wrapper.findAll("tbody tr")).toHaveLength(5);
		expect(wrapper.find(".record-note").text()).toContain("First 5 of 8.");

		await wrapper.find(".record-toggle").trigger("click");

		expect(wrapper.findAll("tbody tr")).toHaveLength(8);
		expect(wrapper.find(".record-note").text()).toContain("All 8 shown.");
	});

	it("keeps the exact request and response on the Raw tab", async () => {
		const wrapper = mount(ToolDetails, { props: { block: LIST } });

		await tab(wrapper, "Raw").trigger("click");

		const [request, response] = wrapper.findAll(".code-preview pre").map((pre) => pre.text());
		expect(JSON.parse(request)).toEqual(LIST.input);
		expect(JSON.parse(response).data).toHaveLength(8);
		expect(wrapper.find("table").exists()).toBe(false);
	});

	// What the runtime sends with a script's result for each call the script made.
	const STEPS = [
		{ tool_name: "list_documents", input: { doctype: "Customer", limit: 2 }, status: "success", duration_ms: 31, count: 40, returned: 2, result: { data: [{ name: "CUST-1" }, { name: "CUST-2" }], total_count: 40 }, error: null },
		{ tool_name: "get_document", input: { doctype: "Customer", name: "CUST-9" }, status: "error", duration_ms: 12, count: null, returned: null, result: null, error: "Customer CUST-9 not found" },
		{ tool_name: "get_document", input: { doctype: "Supplier", name: "S-1" }, status: "stopped", duration_ms: null, count: null, returned: null, result: null, error: null },
	];

	it("opens a script that reports its calls on what it did, in plain words", async () => {
		const wrapper = mount(ToolDetails, { props: { block: { ...SCRIPT, steps: STEPS } } });

		expect(wrapper.findAll(".details-tab").map((button) => button.text())).toEqual(["What it did", "Code", "Output"]);
		expect(wrapper.findAll(".step-label").map((label) => label.text())).toEqual([
			"Listed records → Customer",
			"Read record → Customer",
			"Read record → Supplier",
		]);
		expect(wrapper.findAll(".step-meta").map((meta) => meta.text())).toEqual(["40 found · 31ms"]);
		expect(wrapper.find(".step-reason").text()).toBe("Customer CUST-9 not found");
		expect(wrapper.findAll(".script-step").map((row) => row.find(".status-chip").classes().find((name) => name.startsWith("chip-")))).toEqual([
			"chip-success",
			"chip-error",
			"chip-stopped",
		]);
	});

	it("opens a step onto what it asked for and a preview of what came back", async () => {
		const wrapper = mount(ToolDetails, { props: { block: { ...SCRIPT, steps: STEPS } } });

		await wrapper.findAll(".step-line")[0].trigger("click");

		expect(wrapper.findAll(".summary-pills li").map((pill) => pill.text())).toEqual(["Up to 2"]);
		expect(wrapper.findAll("tbody tr")).toHaveLength(2);
		expect(wrapper.find(".record-note").text()).toContain("2 of 40 returned.");

		await wrapper.findAll(".step-line")[2].trigger("click");
		expect(wrapper.findAll(".summary-plain").at(-1).text()).toContain("did not finish");
	});

	it("says when a script made more steps than it lists, and skips a step the chat has no row for", () => {
		const steps = [...STEPS, { tool_name: "get_skill", input: {}, status: "success" }];
		const wrapper = mount(ToolDetails, { props: { block: { ...SCRIPT, steps, calls: 120 } } });

		expect(wrapper.findAll(".step-label")).toHaveLength(3);
		expect(wrapper.find(".steps-more").text()).toBe("The first 3 of 120 steps.");
	});

	it("does not point a step's reader at a Raw tab the step does not have", async () => {
		const wide = Object.fromEntries(Array.from({ length: 9 }, (_, i) => [`f${i}`, i]));
		const steps = [{ ...STEPS[0], result: { data: [wide] }, count: 1, returned: 1 }];
		const wrapper = mount(ToolDetails, { props: { block: { ...SCRIPT, steps } } });

		await wrapper.find(".step-line").trigger("click");

		expect(wrapper.find(".record-note").text()).toBe("1 record. 3 more columns.");
	});

	it("gains the What it did tab when the steps arrive, without moving the reader", async () => {
		// The drawer was opened while the script was still running: no result and no steps yet.
		const wrapper = mount(ToolDetails, { props: { block: { ...SCRIPT, status: "running", result: null } } });
		expect(wrapper.findAll(".details-tab").map((button) => button.text())).toEqual(["Code", "Output"]);

		await wrapper.setProps({ block: { ...SCRIPT, steps: STEPS } });

		expect(wrapper.findAll(".details-tab").map((button) => button.text())).toEqual(["What it did", "Code", "Output"]);
		expect(tab(wrapper, "Code").attributes("aria-pressed")).toBe("true");
	});

	it("shows a script as numbered lines of code, not as a quoted string", () => {
		const wrapper = mount(ToolDetails, { props: { block: SCRIPT } });

		const lines = wrapper.findAll(".code-line").map((line) => line.text());
		expect(lines).toEqual(['c = await list_documents(doctype="Customer", limit=2)', 'print(c["data"])']);
		expect(wrapper.text()).not.toContain("\\n");
		expect(wrapper.findAll(".details-tab").map((button) => button.text())).toEqual(["Code", "Output"]);
	});

	it("shows the records a script printed as a table", async () => {
		const wrapper = mount(ToolDetails, { props: { block: SCRIPT } });

		await tab(wrapper, "Output").trigger("click");

		expect(wrapper.findAll("th").map((th) => th.text())).toEqual(["Name", "Territory"]);
		expect(wrapper.findAll("tbody tr").map((row) => row.text())).toEqual(["CUST-1North", "CUST-2—"]);
	});

	it("shows each list a script printed by name as its own table", async () => {
		const printed = "{'companies': [{'name': 'Northwind'}], 'companies_total': 5}\n{'customers': [{'name': 'CUST-1'}, {'name': 'CUST-2'}]}";
		const wrapper = mount(ToolDetails, { props: { block: { ...SCRIPT, result: parts(printed) } } });

		await tab(wrapper, "Output").trigger("click");

		expect(wrapper.findAll(".output-title").map((title) => title.text())).toEqual(["Companies", "Customers"]);
		expect(wrapper.findAll("table")).toHaveLength(2);
		expect(wrapper.find(".field-list").text()).toBe("Companies total5");
	});

	it("shows printed words as the words, and a failed script's error as an error", async () => {
		const words = mount(ToolDetails, { props: { block: { ...SCRIPT, result: parts("Total customers: 2") } } });
		await tab(words, "Output").trigger("click");
		expect(words.find(".output-text").text()).toBe("Total customers: 2");

		const failed = mount(ToolDetails, {
			props: { block: { ...SCRIPT, status: "error", result: parts("NameError: name 'custmers' is not defined") } },
		});
		await tab(failed, "Output").trigger("click");
		expect(failed.find(".output-error").text()).toContain("NameError");
	});

	it("says a large live result needs a reload, on each tab that would show it", async () => {
		// block_builder.truncate_result_for_emit sends this over the socket for a result past 8000 characters.
		const live = { _truncated: true, preview: '[{"text": "[{\'name\': \'CUST-1\'}, {", "_note": "full result available on reload' };
		const list = mount(ToolDetails, { props: { block: { ...LIST, result: live } } });
		expect(list.find(".summary-plain").text()).toContain("Reload the page");
		await tab(list, "Raw").trigger("click");
		expect(list.find(".details-plain").text()).toContain("Reload the page");

		const script = mount(ToolDetails, { props: { block: { ...SCRIPT, result: live } } });
		await tab(script, "Output").trigger("click");
		expect(script.find(".output-plain").text()).toContain("printed too much");
	});

	it("says why a failed call failed", () => {
		const wrapper = mount(ToolDetails, {
			props: { block: { ...LIST, status: "error", result: parts({ success: false, error: "No permission for Customer" }) } },
		});

		expect(wrapper.find(".summary-error").text()).toBe("No permission for Customer");
	});

	it("opens the next block on the tab the person last chose, per kind of call", async () => {
		await tab(mount(ToolDetails, { props: { block: LIST } }), "Raw").trigger("click");

		expect(tab(mount(ToolDetails, { props: { block: LIST } }), "Raw").attributes("aria-pressed")).toBe("true");
		// A script has other tabs: it opens on its own first one, and a choice made there is its own.
		const script = mount(ToolDetails, { props: { block: SCRIPT } });
		expect(tab(script, "Code").attributes("aria-pressed")).toBe("true");
		await tab(script, "Output").trigger("click");

		expect(tab(mount(ToolDetails, { props: { block: SCRIPT } }), "Output").attributes("aria-pressed")).toBe("true");
		expect(tab(mount(ToolDetails, { props: { block: LIST } }), "Raw").attributes("aria-pressed")).toBe("true");
	});

	it("copies the script from the Code tab", async () => {
		let copiedText = null;
		// jsdom has no clipboard; the browser's is what the Copy button writes to.
		Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async (text) => (copiedText = text) } });
		const wrapper = mount(ToolDetails, { props: { block: SCRIPT } });

		const copy = wrapper.findAll(".code-toggle").find((button) => button.text() === "Copy");
		await copy.trigger("click");
		await flushPromises();

		expect(copiedText).toBe(SCRIPT.input.code);
		expect(copy.text()).toBe("Copied");
	});
});
