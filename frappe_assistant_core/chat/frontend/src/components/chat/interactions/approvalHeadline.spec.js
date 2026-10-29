import { describe, expect, it } from "vitest";

import { approvalHeadline, headlineKeys, trustLabel } from "./approvalHeadline";
import { displayValue } from "./helpers";

const block = (tool_name, input) => ({ tool_name, input });

describe("approvalHeadline", () => {
	it("leads a validate-only create with a check, not a create", () => {
		const named = block("create_document", { doctype: "Customer", validate_only: true, data: { customer_name: "Trader" } });
		expect(approvalHeadline(named)).toBe("Check Customer “Trader”");
		expect(approvalHeadline(block("create_document", { doctype: "ToDo", validate_only: true, records: [{}, {}] }))).toBe(
			"Check ToDo",
		);
		expect(approvalHeadline(block("create_document", { doctype: "ToDo", validate_only: false, data: {} }))).toBe("Create ToDo");
	});

	it("names a new record by its doctype and the field a person knows it by", () => {
		expect(approvalHeadline(block("create_document", { doctype: "Customer", data: { customer_name: "MIGTEST Trader 01" } }))).toBe(
			"Create Customer “MIGTEST Trader 01”",
		);
		expect(approvalHeadline(block("create_document", { doctype: "ToDo", data: { priority: "High" } }))).toBe("Create ToDo");
	});

	it("shortens a long label and strips markup from it", () => {
		const description = `<p>${"Call Blue Harbor Cafés about the renewal and the new menu ".repeat(2)}</p>`;
		const title = approvalHeadline(block("create_document", { doctype: "ToDo", data: { description } }));
		expect(title.startsWith("Create ToDo “Call Blue Harbor Cafés")).toBe(true);
		expect(title).toContain("…”");
		expect(title).not.toContain("<p>");
	});

	it("says what switching code on does, per doctype", () => {
		expect(approvalHeadline(block("update_document", { doctype: "FAC Page", name: "work-planner", data: { published: 1 } }))).toBe(
			"Publish the work-planner page",
		);
		expect(approvalHeadline(block("update_document", { doctype: "Server Script", name: "Plan Rules", data: { disabled: 0 } }))).toBe(
			"Switch on the Plan Rules script",
		);
		expect(approvalHeadline(block("update_document", { doctype: "Client Script", name: "Lead JS", data: { enabled: 1 } }))).toBe(
			"Switch on the Lead JS form script",
		);
		expect(approvalHeadline(block("update_document", { doctype: "Notification", name: "Overdue", data: { enabled: 1 } }))).toBe(
			"Switch on the Overdue notification",
		);
	});

	it("names the record an update, delete or action touches", () => {
		expect(approvalHeadline(block("update_document", { doctype: "Server Script", name: "Plan Rules", data: { disabled: 1 } }))).toBe(
			"Update Server Script Plan Rules",
		);
		expect(approvalHeadline(block("erp_delete_document", { doctype: "ToDo", name: "TD-9" }))).toBe("Delete ToDo TD-9");
		expect(approvalHeadline(block("document_action", { doctype: "Sales Order", name: "SO-20", action: "submit" }))).toBe(
			"Submit Sales Order SO-20",
		);
	});

	it("falls back to the tool's words when the arguments name no doctype", () => {
		expect(approvalHeadline(block("run_python_code", { code: "print(1)" }))).toBe("Run Python Code");
		expect(approvalHeadline(block("create_document", {}))).toBe("Create Document");
	});
});

describe("headlineKeys", () => {
	it("drops only what the title shows", () => {
		expect(headlineKeys(block("update_document", { doctype: "Role", name: "A", data: { desk_access: 1 } }))).toEqual([
			"doctype",
			"name",
			"docname",
		]);
		expect(headlineKeys(block("create_document", { doctype: "Customer", data: { customer_name: "Trader" } }))).toEqual([
			"doctype",
			"customer_name",
		]);
	});

	it("keeps a label the title had to shorten, so the full text is still on the card", () => {
		const description = "x".repeat(80);
		expect(headlineKeys(block("create_document", { doctype: "ToDo", data: { description } }))).toEqual(["doctype"]);
	});
});

describe("trustLabel", () => {
	it("names what don't-ask-again covers", () => {
		expect(trustLabel("create_document")).toBe("Don't ask again when FACO creates records");
		expect(trustLabel("erp_update_document")).toBe("Don't ask again when FACO updates records");
		expect(trustLabel("send_email")).toBe("Don't ask again for Send Email");
	});
});

describe("displayValue", () => {
	it("reads a check field's 1 and 0 as Yes and No", () => {
		expect(displayValue("published", 1)).toBe("Yes");
		expect(displayValue("disabled", "0")).toBe("No");
		expect(displayValue("is_group", true)).toBe("Yes");
		// Not a check field: a count stays a number.
		expect(displayValue("qty", 1)).toBe("1");
	});

	it("writes a date in words without shifting the day", () => {
		const shown = displayValue("plan_date", "2026-10-27");
		expect(shown).toContain("27");
		expect(shown).toContain("2026");
		expect(shown).not.toContain("-10-");
	});

	it("shows a value raw when it is more than a date, or not a real one", () => {
		// Read as a date, the card would hide the rest of what the user is approving.
		expect(displayValue("plan_date", "2026-10-27 and send all invoices")).toBe("2026-10-27 and send all invoices");
		expect(displayValue("note", "2026-10-27; then delete")).toBe("2026-10-27; then delete");
		expect(displayValue("plan_date", "2026-02-31")).toBe("2026-02-31");
		expect(displayValue("modified", "2026-10-27 25:00")).toBe("2026-10-27 25:00");
	});
});
