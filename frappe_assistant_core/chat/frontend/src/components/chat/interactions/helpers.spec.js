import { describe, it, expect } from "vitest";
import {
	flattenInput,
	isMoneyKey,
	isDateValue,
	isMonoValue,
	splitDetailFields,
	CODE_KEYS,
	isCodeKey,
	codeLanguage,
	isChildTable,
} from "./helpers";

describe("isMoneyKey", () => {
	it("matches money-like keys case-insensitively", () => {
		for (const k of ["grand_total", "Rate", "conversion_rate", "net_total", "qty", "discount_amount"]) {
			expect(isMoneyKey(k)).toBe(true);
		}
	});
	it("does not match non-money keys", () => {
		for (const k of ["customer", "doctype", "title", "company"]) {
			expect(isMoneyKey(k)).toBe(false);
		}
	});
});

describe("isDateValue", () => {
	it("matches ISO dates and datetimes", () => {
		expect(isDateValue("2025-04-30")).toBe(true);
		expect(isDateValue("2025-04-30 14:05:00")).toBe(true);
		expect(isDateValue("2025-04-30T14:05")).toBe(true);
	});
	it("rejects non-dates", () => {
		expect(isDateValue("Promantia")).toBe(false);
		expect(isDateValue(42)).toBe(false);
		expect(isDateValue(null)).toBe(false);
	});
});

describe("isMonoValue", () => {
	it("is true for money keys, date keys, and date-shaped values", () => {
		expect(isMonoValue("grand_total", 1500)).toBe(true);
		expect(isMonoValue("delivery_date", "2025-04-30")).toBe(true);
		expect(isMonoValue("posting_date", "anything")).toBe(true);
		expect(isMonoValue("note", "2025-04-30")).toBe(true);
	});
	it("is false for plain text fields", () => {
		expect(isMonoValue("customer", "Promantia")).toBe(false);
		expect(isMonoValue("currency", "INR")).toBe(false);
	});
});

describe("flattenInput on an update that renames", () => {
	it("keeps a data key that collides with the record name as a new value", () => {
		const flat = flattenInput({ doctype: "Server Script", name: "Old Script", data: { name: "New Script" } });
		expect(flat).toEqual({ doctype: "Server Script", name: "Old Script", new_name: "New Script" });
	});

	it("keeps top-level rename keys and other keys beside data", () => {
		const flat = flattenInput({ doctype: "Role", name: "A", new_name: "B", merge: true, data: { desk_access: 1 } });
		expect(flat).toMatchObject({ doctype: "Role", name: "A", new_name: "B", merge: true, desk_access: 1 });
	});

	it("does not duplicate a data key that restates the same value", () => {
		const flat = flattenInput({ doctype: "ToDo", name: "T1", data: { name: "T1", status: "Open" } });
		expect(flat).toEqual({ doctype: "ToDo", name: "T1", status: "Open" });
	});

	it("shows the rename ahead of other changed fields", () => {
		const flat = flattenInput({ doctype: "Server Script", name: "Old", data: { disabled: 1, name: "New" } });
		const keys = splitDetailFields(flat, 3).primary.map(([k]) => k);
		expect(keys).toEqual(["doctype", "name", "new_name"]);
	});
});

describe("splitDetailFields", () => {
	const flat = flattenInput({
		doctype: "Sales Order",
		customer: "Promantia",
		company: "Frappe Assistant Cloud",
		order_type: "Sales",
		transaction_date: "2025-04-17",
		delivery_date: "2025-04-30",
		currency: "INR",
		conversion_rate: 1,
		selling_price_list: "Standard Selling",
		grand_total: 1500,
	});

	it("orders priority keys first and keeps doctype + customer in the primary set", () => {
		const { primary } = splitDetailFields(flat, 4);
		const keys = primary.map(([k]) => k);
		expect(keys[0]).toBe("doctype");
		expect(keys).toContain("customer");
		expect(primary.length).toBe(4);
	});

	it("pushes the remaining fields into overflow with a correct count", () => {
		const { overflow, overflowCount } = splitDetailFields(flat, 4);
		expect(overflowCount).toBe(overflow.length);
		expect(overflowCount).toBe(Object.keys(flat).length - 4);
		expect(overflowCount).toBe(6); // matches mockup "+ 6 more"
	});

	it("handles empty/undefined input without throwing", () => {
		expect(splitDetailFields(undefined).primary).toEqual([]);
		expect(splitDetailFields({}).overflowCount).toBe(0);
	});
});

describe("formatToolName", () => {
	it("keeps acronyms upper case", async () => {
		const { formatToolName } = await import("./helpers");
		expect(formatToolName("add_crm_activity")).toBe("Add CRM Activity");
		expect(formatToolName("convert_crm_lead")).toBe("Convert CRM Lead");
		expect(formatToolName("create_document")).toBe("Create Document");
	});
});

describe("code keys", () => {
	it("lists the fields that hold code", () => {
		expect(CODE_KEYS).toEqual([
			"script",
			"condition",
			"query",
			"html",
			"javascript",
			"report_script",
			"css",
			"message",
		]);
		expect(isCodeKey("script")).toBe(true);
		expect(isCodeKey("subject")).toBe(false);
	});

	it("picks the language from the key and doctype", () => {
		expect(codeLanguage("script", "Server Script")).toBe("python");
		expect(codeLanguage("report_script", "Report")).toBe("python");
		expect(codeLanguage("condition", "Notification")).toBe("python");
		expect(codeLanguage("javascript", "Report")).toBe("javascript");
		expect(codeLanguage("query", "Report")).toBe("sql");
		expect(codeLanguage("html", "Print Format")).toBe("django");
		expect(codeLanguage("html", "Web Page")).toBe("xml");
		expect(codeLanguage("css", "Print Format")).toBe("xml");
	});
});

describe("isChildTable", () => {
	it("is true only for a non-empty array of plain objects", () => {
		expect(isChildTable([{ state: "A" }])).toBe(true);
		expect(isChildTable([])).toBe(false);
		expect(isChildTable(["a"])).toBe(false);
		expect(isChildTable("x")).toBe(false);
	});
});
