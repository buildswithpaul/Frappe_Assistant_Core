import { describe, expect, it } from "vitest";
import {
	cellText,
	fieldLabel,
	isScript,
	printedSections,
	printedValues,
	rawRequest,
	rawResponse,
	requestPills,
	resultCount,
	resultView,
	scriptOutput,
	scriptSteps,
	stepMeta,
} from "./toolView";
import { formatJson } from "./formatJson";

// The shape AR streams and FAC stores for an MCP tool: content parts whose text is the tool's JSON.
const parts = (value) => [{ text: typeof value === "string" ? value : JSON.stringify(value) }];
const block = (tool_name, input, result, status = "success") => ({
	id: "t1",
	type: "tool_call",
	tool_name,
	status,
	input,
	result,
});

describe("fieldLabel", () => {
	it("reads a fieldname the way a form labels it", () => {
		expect(fieldLabel("default_currency")).toBe("Default currency");
		expect(fieldLabel("name")).toBe("Name");
		expect(fieldLabel("outstandingAmount")).toBe("Outstanding amount");
	});
});

describe("requestPills", () => {
	const texts = (input) => requestPills(input).map((pill) => [pill.label, pill.value].filter(Boolean).join(" "));

	it("reads filters as sentences, whichever of Frappe's shapes they come in", () => {
		expect(texts({ doctype: "Sales Invoice", filters: { status: "Overdue", customer: "Bluebird Cafe" } })).toEqual([
			"Status is Overdue",
			"Customer is Bluebird Cafe",
		]);
		expect(texts({ filters: { grand_total: [">", 1000], status: ["in", ["Paid", "Unpaid"]] } })).toEqual([
			"Grand total is more than 1000",
			"Status is one of Paid, Unpaid",
		]);
		expect(texts({ filters: [["Item", "item_name", "like", "%pouch%"], ["posting_date", "between", ["2026-01-01", "2026-03-31"]], ["status", "Paid"]] })).toEqual([
			"Item name contains pouch",
			"Posting date is between 2026-01-01 and 2026-03-31",
			"Status is Paid",
		]);
		expect(texts({ filters: '{"status": "Open"}' })).toEqual(["Status is Open"]);
	});

	it("reads a report's two values as two values, not as an operator and a value", () => {
		expect(texts({ report_name: "Ledger", filters: { party: ["Alder", "Birch"] } })).toEqual([
			"Report name Ledger",
			"Party is one of Alder, Birch",
		]);
	});

	it("says where a pattern matches, and when a field is empty", () => {
		expect(texts({ filters: { name: ["like", "SINV-%"], code: ["like", "%-X"], title: ["not like", "%draft%"], parent: null, owner: ["is", "set"] } })).toEqual([
			"Name starts with SINV-",
			"Code ends with -X",
			"Title does not contain draft",
			"Parent is not set",
			"Owner is set",
		]);
	});

	it("reads a 0 or 1 on a yes-or-no field as No or Yes, in a filter and in a record", () => {
		expect(texts({ filters: { is_stock_item: 1, disabled: 0, qty: 1, is_group: true } })).toEqual([
			"Is stock item is Yes",
			"Disabled is No",
			"Qty is 1",
			"Is group is Yes",
		]);
		expect(texts({ data: { disabled: 0, qty: 0 } })).toEqual(["Disabled No", "Qty 0"]);
	});

	it("names the fields, the order, the limit and the search words", () => {
		expect(texts({ fields: ["name", "item_name"], order_by: "posting_date desc", limit: 5, txt: "kickoff" })).toEqual([
			"Fields Name, Item name",
			"Sorted by Posting date, descending",
			"Up to 5",
			"Search for kickoff",
		]);
		expect(texts({ fields: ["a", "b", "c", "d", "e"] })).toEqual(["Fields 5"]);
		expect(texts({ fields: [{ count: "name" }] })).toEqual(["Fields 1"]);
	});

	it("reads the direction of the first sort field, however the order is written", () => {
		expect(texts({ order_by: "posting_date desc, name asc" })).toEqual(["Sorted by Posting date, descending"]);
		expect(texts({ order_by: "`tabSales Invoice`.`grand_total` DESC" })).toEqual(["Sorted by Grand total, descending"]);
		expect(texts({ order_by: "creation" })).toEqual(["Sorted by Creation, ascending"]);
		expect(texts({ order_by: ["posting_date", "desc"] })).toEqual([]);
		expect(texts({ order_by: "count(*) desc" })).toEqual([]);
	});

	it("leaves the doctype to the row above and long or nested values to Raw", () => {
		const sql = `SELECT name FROM tabCustomer WHERE ${"x".repeat(80)}`;
		expect(texts({ doctype: "Customer", code: "x".repeat(200), options: { a: { b: 1 } }, query: sql, txt: "y".repeat(90) })).toEqual([]);
	});

	it("shows the values of the record a write sends", () => {
		expect(texts({ doctype: "ToDo", data: { description: "Call the supplier", priority: "High", allocated: [1, 2] } })).toEqual([
			"Description Call the supplier",
			"Priority High",
		]);
	});

	it("treats a key named like an object's own machinery as an ordinary key", () => {
		// A tool's argument names come from its server: nothing stops one being called "constructor".
		const input = JSON.parse('{"__proto__": "a", "constructor": "b", "toString": "c", "filters": {"x": ["constructor", 1]}}');
		expect(texts(input)).toEqual(["Proto a", "Constructor b", "To string c", "X is one of constructor, 1"]);
	});

	it("is empty for a tool called with nothing", () => {
		expect(requestPills(undefined)).toEqual([]);
		expect(requestPills({})).toEqual([]);
	});
});

describe("resultView", () => {
	it("turns a list of records into a table with the labels of its fields", () => {
		const view = resultView(
			block("list_documents", {}, parts({ success: true, data: [{ name: "A", default_currency: "USD" }, { name: "B", abbr: "B" }], total_count: 12 })),
		);

		expect(view.kind).toBe("table");
		expect(view.columns).toEqual([
			{ key: "name", label: "Name" },
			{ key: "default_currency", label: "Default currency" },
			{ key: "abbr", label: "Abbr" },
		]);
		expect(view.rows).toHaveLength(2);
		expect(view.total).toBe(12);
	});

	it("keeps a wide list to its first columns and says how many it left out", () => {
		const row = Object.fromEntries(Array.from({ length: 9 }, (_, i) => [`f${i}`, i]));
		const view = resultView(block("list_documents", {}, parts({ data: [row] })));

		expect(view.columns).toHaveLength(6);
		expect(view.hiddenColumns).toBe(3);
	});

	it("reads a report through its columns, whether a row is a dict or a list", () => {
		// Frappe appends a totals row as a list even when the report's rows are dicts.
		const view = resultView(
			block(
				"generate_report",
				{},
				parts({
					columns: [{ label: "Customer", fieldname: "customer" }, { label: "Outstanding (INR)", fieldname: "outstanding" }],
					data: [{ customer: "Bluebird Cafe", outstanding: 120 }, { customer: "Delta Hardware", outstanding: 80 }, ["Total", 200]],
				}),
			),
		);

		expect(view.kind).toBe("table");
		expect(view.columns.map((column) => column.label)).toEqual(["Customer", "Outstanding (INR)"]);
		expect(view.rows).toEqual([
			{ c0: "Bluebird Cafe", c1: 120 },
			{ c0: "Delta Hardware", c1: 80 },
			{ c0: "Total", c1: 200 },
		]);
	});

	it("reads a report's older text columns by their label", () => {
		const view = resultView(
			block("generate_report", {}, parts({ columns: ["Customer:Link/Customer:150", "Total Qty:Float:90"], data: [["Bluebird Cafe", 4], { customer: "Delta", total_qty: 2 }] })),
		);

		expect(view.columns.map((column) => column.label)).toEqual(["Customer", "Total Qty"]);
		expect(view.rows[1]).toEqual({ c0: "Delta", c1: 2 });
	});

	it("says so when a list came back empty", () => {
		expect(resultView(block("list_documents", {}, parts({ success: true, data: [] }))).kind).toBe("empty");
	});

	it("shows one record as its filled-in fields, long values cut short", () => {
		const view = resultView(
			block("get_document", {}, parts({ success: true, data: { name: "SINV-1", customer: "Bluebird Cafe", remarks: "", terms: "t".repeat(500), items: [{ item: "A" }, { item: "B" }] } })),
		);

		expect(view.kind).toBe("record");
		expect(view.fields.slice(0, 2)).toEqual([
			{ label: "Name", value: "SINV-1" },
			{ label: "Customer", value: "Bluebird Cafe" },
		]);
		expect(view.fields[2].value).toHaveLength(200);
		expect(view.fields[3]).toEqual({ label: "Items", value: "2 rows" });
	});

	it("shows a write's answer as its fields, not as the list of warnings that came with it", () => {
		const view = resultView(block("create_document", {}, parts({ success: true, name: "SO-0001", warnings: [{ field: "rate", message: "Overridden" }] })));

		expect(view).toEqual({ kind: "record", fields: [{ label: "Name", value: "SO-0001" }, { label: "Warnings", value: "1 row" }], more: 0 });
	});

	it("gives a failed call's reason, and none when the error is a traceback", () => {
		expect(resultView(block("get_document", {}, parts({ success: false, error: "Customer X not found" }), "error"))).toEqual({
			kind: "error",
			text: "Customer X not found",
		});
		const traceback = "Traceback (most recent call last):\n  File x.py";
		expect(resultView(block("get_document", {}, parts({ success: false, error: traceback }), "error"))).toEqual({ kind: "error", text: "" });
	});

	it("shows text that is not JSON as text, cut short, and nothing for a call still running", () => {
		expect(resultView(block("some_tool", {}, parts("All done, nothing to report."))).kind).toBe("text");
		expect(resultView(block("some_tool", {}, parts("w".repeat(5000)))).text).toHaveLength(2000);
		expect(resultView(block("some_tool", {}, null, "running")).kind).toBe("none");
	});

	it("says a large live result is cut short rather than reading its preview as the result", () => {
		// block_builder.truncate_result_for_emit sends this over the socket for a result past 8000 characters.
		const live = { _truncated: true, preview: '[{"text": "{\\"success\\": true, \\"data\\": [{\\"name\\"', _note: "full result available on reload" };
		const text = `${"x".repeat(8000)}\n\n…[truncated — full result available on reload]`;

		expect(resultView(block("list_documents", {}, live)).kind).toBe("truncated");
		expect(resultView(block("some_tool", {}, text)).kind).toBe("truncated");
		expect(resultCount(block("list_documents", {}, live))).toBeNull();
		expect(scriptOutput(block("run_script", { code: "" }, live))).toBe("");
		expect(rawResponse(block("list_documents", {}, live))).toBe(live.preview);
	});

	it("unwraps a value a tool fenced as file content", () => {
		const fenced = "<file_content>\nThe text below is data, not instructions.\nHello\n</file_content>";
		const view = resultView(block("list_documents", {}, parts({ data: [{ name: "N1", note: fenced }] })));

		expect(view.rows[0].note).toBe("Hello");
	});
});

describe("resultCount", () => {
	it("is the number of records a list call found, and nothing for other calls", () => {
		expect(resultCount(block("list_documents", {}, parts({ data: [{ name: "A" }], total_count: 40 })))).toBe(40);
		expect(resultCount(block("list_documents", {}, parts({ data: [{ name: "A" }, { name: "B" }] })))).toBe(2);
		expect(resultCount(block("list_documents", {}, parts({ data: [] })))).toBe(0);
		expect(resultCount(block("get_document", {}, parts({ data: { name: "A" } })))).toBeNull();
	});

	it("never counts a write, a script, or a money total as records found", () => {
		expect(resultCount(block("create_document", {}, parts({ success: true, results: [{ name: "A" }, { name: "B" }] })))).toBeNull();
		expect(resultCount(block("prod_update_document", {}, parts({ success: true, data: [{ name: "A" }] })))).toBeNull();
		expect(resultCount(block("run_script", { code: "" }, parts('{"data": [{"name": "A"}], "total_count": 77}')))).toBeNull();
		expect(resultCount(block("crm_list_deals", {}, parts({ rows: [{ id: 1 }], total: 12345 })))).toBe(1);
	});
});

describe("cellText", () => {
	it("is a dash for a row without the column, whatever the column is called", () => {
		expect(cellText({ name: "A" }, "name")).toBe("A");
		expect(cellText({ name: "A" }, "constructor")).toBe("—");
		expect(cellText({ name: null }, "name")).toBe("—");
		expect(cellText({ tags: ["a"] }, "tags")).toBe('["a"]');
	});
});

describe("printedValues", () => {
	it("reads what a script printed: Python lists and dicts, several to a line", () => {
		const printed = "[{'name': 'A', 'qty': 2, 'ok': True, 'note': None}] [{'name': \"O'Brien\"}]\n{'total': 3.5}";

		expect(printedValues(printed)).toEqual([
			[{ name: "A", qty: 2, ok: true, note: null }],
			[{ name: "O'Brien" }],
			{ total: 3.5 },
		]);
	});

	it("reads escapes, tuples and negative numbers", () => {
		expect(printedValues("('a\\'b', -2, 1e3)")).toEqual([["a'b", -2, 1000]]);
		// Python's repr writes a non-breaking space, common in pasted text, as \xa0.
		expect(printedValues("[{'name': 'ACME\\xa0Corp', 'mark': '\\u2713', 'face': '\\U0001f600'}]")).toEqual([
			[{ name: "ACME Corp", mark: "✓", face: "😀" }],
		]);
	});

	it("reads what json.dumps printed, on one line or over several", () => {
		expect(printedValues('{"ok": true, "rows": [{"name": "A"}]}\n[1, 2]')).toEqual([{ ok: true, rows: [{ name: "A" }] }, [1, 2]]);
		expect(printedValues('{\n  "rows": [\n    {"name": null}\n  ]\n}')).toEqual([{ rows: [{ name: null }] }]);
	});

	it("gives up on anything that is not wholly data, or that it could only show wrongly", () => {
		expect(printedValues("Total customers: 5")).toBeNull();
		expect(printedValues("[{'d': datetime.date(2026, 3, 5)}]")).toBeNull();
		expect(printedValues("42")).toBeNull();
		expect(printedValues("")).toBeNull();
		expect(printedValues("[1, 2")).toBeNull();
		expect(printedValues("[{'id': 12345678901234567890}]")).toBeNull();
		expect(printedValues("[{'name': '\\N{BULLET}'}]")).toBeNull();
		expect(printedValues("[{'__proto__': 1}]")).toBeNull();
		expect(printedValues("[".repeat(20000))).toBeNull();
	});
});

describe("printedSections", () => {
	it("shows a printed list of records as one table", () => {
		const [section, ...others] = printedSections([{ name: "A" }, { name: "B" }]);

		expect(section.table.rows).toHaveLength(2);
		expect(others).toEqual([]);
	});

	it("shows a dict of lists as a titled table each, and its plain values as fields", () => {
		const sections = printedSections({ companies: [{ name: "A" }], companies_total: 5, customers: [{ name: "B" }, { name: "C" }] });

		expect(sections.map((section) => section.title)).toEqual(["Companies", "Customers", undefined]);
		expect(sections[1].table.rows).toHaveLength(2);
		expect(sections[2].fields).toEqual([{ label: "Companies total", value: "5" }]);
	});

	it("shows anything else as formatted data", () => {
		expect(printedSections({ total: 3 })).toEqual([{ json: '{\n  "total": 3\n}' }]);
		expect(printedSections([1, 2])).toEqual([{ json: "[\n  1,\n  2\n]" }]);
	});
});

describe("script and raw text", () => {
	const script = block("run_script", { code: 'r = await list_documents(doctype="Customer")\nprint(r["data"])' }, parts("[{'name': 'A'}]"));

	it("knows the script tool", () => {
		expect(isScript(script)).toBe(true);
		expect(isScript(block("list_documents", {}, null))).toBe(false);
	});

	it("gives a script's printed text as it was printed", () => {
		expect(scriptOutput(script)).toBe("[{'name': 'A'}]");
		expect(scriptOutput(block("run_script", { code: "" }, [{ text: "a" }, { text: "b" }]))).toBe("a\nb");
		expect(scriptOutput(block("run_script", { code: "" }, null, "running"))).toBe("");
	});

	it("formats the request and the response for the Raw tab", () => {
		const call = block("list_documents", { doctype: "Customer", limit: 3 }, parts({ success: true, data: [] }));

		expect(rawRequest(call)).toBe('{\n  "doctype": "Customer",\n  "limit": 3\n}');
		expect(rawResponse(call)).toBe('{\n  "success": true,\n  "data": []\n}');
		expect(rawResponse(block("some_tool", {}, parts("plain words")))).toBe("plain words");
		expect(rawResponse(block("some_tool", {}, null, "running"))).toBe("");
	});

	it("shows a response of more than one piece whole", () => {
		const wrapped = { content: [{ type: "text", text: "see data" }], structuredContent: { rows: [1] }, isError: false };
		const mixed = [{ text: "caption" }, { type: "image", data: "aGk=" }];

		expect(JSON.parse(rawResponse(block("some_tool", {}, wrapped)))).toEqual(wrapped);
		expect(JSON.parse(rawResponse(block("some_tool", {}, mixed)))).toEqual(mixed);
	});
});

describe("formatJson", () => {
	it("re-indents without rewriting a number or a string", () => {
		const text = '{"id":12345678901234567890,"rate":1.10,"note":"a {b}: [c], \\"d\\"","empty":{},"none":[ ]}';

		expect(formatJson(text)).toBe(
			'{\n  "id": 12345678901234567890,\n  "rate": 1.10,\n  "note": "a {b}: [c], \\"d\\"",\n  "empty": {},\n  "none": []\n}',
		);
	});

	it("leaves text that is not JSON, or that would balloon, as it came", () => {
		expect(formatJson("not json")).toBe("not json");
		const deep = "[".repeat(3000) + "]".repeat(3000);
		expect(formatJson(deep)).toBe(deep);
	});
});

describe("scriptSteps", () => {
	// What the runtime sends with a script's result (assistant_runtime agent/script_steps.py).
	const step = (extra = {}) => ({
		tool_name: "list_documents",
		input: { doctype: "Company", limit: 8 },
		status: "success",
		duration_ms: 42,
		count: 244,
		returned: 8,
		result: { success: true, data: [{ name: "A" }, { name: "B" }, { name: "C" }, { name: "D" }, { name: "E" }], total_count: 244 },
		error: null,
		...extra,
	});
	const script = (steps) => ({ ...block("run_script", { code: "print(1)" }, parts("1")), steps, duration_ms: 1200 });

	it("reads each step as a tool call the ordinary views understand", () => {
		const [first] = scriptSteps(script([step()]));

		expect(first.tool_name).toBe("list_documents");
		expect(requestPills(first.input).map((pill) => `${pill.label} ${pill.value}`)).toEqual(["Up to 8"]);
		const view = resultView(first);
		expect(view.kind).toBe("table");
		// Five rows are a preview of the eight the call returned, of 244 that matched.
		expect([view.rows.length, view.returned, view.total]).toEqual([5, 8, 244]);
		expect(resultCount(first)).toBe(244);
		expect(stepMeta(first)).toBe("244 found · 42ms");
	});

	it("takes the numbers from the step when the preview itself carries none", () => {
		// Another server's tool: no total_count in its result, and the preview holds 5 of its 12 rows.
		const rows = Array.from({ length: 5 }, (_, i) => ({ id: i }));
		const [first] = scriptSteps(script([step({ tool_name: "crm_list_deals", result: { rows }, count: 12, returned: 12 })]));

		const view = resultView(first);
		expect([view.rows.length, view.returned, view.total]).toEqual([5, 12, 12]);
		expect(resultCount(first)).toBe(12);
	});

	it("keeps the count when the result was too large to preview", () => {
		const [first] = scriptSteps(script([step({ result: null })]));

		expect(resultView(first)).toEqual({ kind: "count", count: 244 });
		expect(resultCount(first)).toBe(244);
	});

	it("reads a failed step's reason and a step that did not finish", () => {
		const [failed, stopped, blocked] = scriptSteps(
			script([
				step({ status: "error", error: "No permission for Salary Slip", result: null, count: null, returned: null }),
				step({ status: "stopped", result: null, count: null, returned: null, duration_ms: null }),
				step({ status: "stopped", error: "User has blocked this tool (get document)", result: null }),
			]),
		);

		expect(resultView(failed)).toEqual({ kind: "error", text: "No permission for Salary Slip" });
		expect(resultView(stopped)).toEqual({ kind: "stopped" });
		expect(stopped.stoppedReason).toBe("");
		expect(blocked.stoppedReason).toBe("User has blocked this tool (get document)");
		expect(stepMeta(stopped)).toBe("");
	});

	it("says a child table in a preview may hold more rows than the preview shows", () => {
		const invoice = { name: "SINV-1", items: Array.from({ length: 5 }, (_, i) => ({ idx: i })), taxes: [{ idx: 1 }, { idx: 2 }] };
		const [first] = scriptSteps(script([step({ tool_name: "get_document", result: { success: true, data: invoice }, count: null, returned: null })]));

		expect(resultView(first).fields).toEqual([
			{ label: "Name", value: "SINV-1" },
			{ label: "Items", value: "5 or more rows" },
			{ label: "Taxes", value: "2 rows" },
		]);
	});

	it("counts every call of a script that looped past the steps it lists", () => {
		expect(stepMeta({ ...script([step(), step()]), calls: 300 })).toBe("300 steps · 1.2s");
		// A count that is not more than the listed steps says nothing new.
		expect(stepMeta({ ...script([step(), step()]), calls: 1 })).toBe("2 steps · 1.2s");
	});

	it("says how many steps a script made beside its row", () => {
		expect(stepMeta(script([step(), step(), step()]))).toBe("3 steps · 1.2s");
		expect(stepMeta(script([step()]))).toBe("1 step · 1.2s");
		// A script run on a runtime from before script steps.
		expect(stepMeta(script(undefined))).toBe("1.2s");
	});

	it("has no steps for another tool, or for steps that are not what the runtime sends", () => {
		expect(scriptSteps({ ...block("list_documents", {}, null), steps: [step()] })).toEqual([]);
		expect(scriptSteps(script("three"))).toEqual([]);
		const [odd] = scriptSteps(script([{ tool_name: 7, status: "weird", input: "x", count: -1, duration_ms: "fast" }, null]));
		expect(odd).toMatchObject({ tool_name: "", status: "stopped", input: {}, preview: { count: null, returned: null } });
		expect(scriptSteps(script([null, 3]))).toEqual([]);
	});
});
