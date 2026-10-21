import { describe, it, expect } from "vitest";
import { customisationConsequence, isCustomisationRisk, writeConsequence } from "./customisation";

describe("writeConsequence", () => {
	it("states the write effect for record tools", () => {
		expect(writeConsequence("create_document", {})).toBe("This will write a new record to your ERP");
		expect(writeConsequence("update_document", {})).toBe("This will modify an existing record in your ERP");
		expect(writeConsequence("delete_document", {})).toBe("This will permanently delete a record from your ERP");
	});

	it("follows the requested document action", () => {
		expect(writeConsequence("document_action", { action: "cancel" })).toContain("cancel a submitted record");
		expect(writeConsequence("document_action", {})).toContain("submit a record");
		expect(writeConsequence("document_action", { action: "weird" })).toContain("submit, cancel or amend");
	});

	it("says nothing for tools that may not write", () => {
		expect(writeConsequence("ask_user", {})).toBe("");
	});
});

describe("customisationConsequence", () => {
	const create = (doctype, data) => ({ doctype, data });

	it("says when a server script runs", () => {
		const text = (event, doctype = "Sales Invoice") =>
			customisationConsequence("create_document", create("Server Script", { script_type: "DocType Event", reference_doctype: doctype, doctype_event: event }));
		expect(text("Before Submit")).toBe("This code will run every time someone submits a Sales Invoice");
		expect(text("Before Save")).toContain("someone saves a");
		expect(text("After Save")).toContain("someone saves a");
		expect(text("Before Cancel")).toContain("someone cancels a");
		expect(text("After Insert")).toContain("someone uses a");
		expect(text("Before Save", "Item")).toBe("This code will run every time someone saves an Item");
	});

	it("describes API and scheduler scripts", () => {
		expect(customisationConsequence("create_document", create("Server Script", { script_type: "API" }))).toBe(
			"This code will run on the server when called",
		);
		expect(customisationConsequence("update_document", create("Server Script", { script_type: "Scheduler Event" }))).toBe(
			"This code will run on a schedule",
		);
	});

	it("covers the other customisation doctypes", () => {
		const c = (doctype, data = {}) => customisationConsequence("create_document", create(doctype, data));
		expect(c("Client Script", { dt: "Lead" })).toBe("This changes how the Lead form behaves in Desk for everyone");
		expect(c("Custom Field", { dt: "Item" })).toBe("Adds a field to every Item");
		expect(c("Property Setter", { doc_type: "Item" })).toBe("Changes how an Item field behaves for everyone");
		expect(c("Workflow", { document_type: "Leave Application" })).toBe(
			"Changes how Leave Application records are approved for everyone",
		);
		expect(c("Print Format", { doc_type: "Quotation" })).toBe("Changes how Quotation prints");
		expect(c("Notification", { document_type: "Lead" })).toBe("Sends messages automatically when Lead records change");
		expect(c("Report", { ref_doctype: "Sales Order" })).toBe("Adds a report on Sales Order");
		for (const dt of ["Role", "Custom DocPerm", "DocType"]) {
			expect(c(dt)).toBe("Changes who can see or do what on this site");
		}
	});

	it("warns on any customisation delete and ignores ordinary records", () => {
		expect(customisationConsequence("delete_document", { doctype: "Client Script", name: "x" })).toBe(
			"This removes a customisation from your site for everyone",
		);
		expect(customisationConsequence("create_document", create("ToDo", {}))).toBe(null);
		expect(customisationConsequence("delete_document", { doctype: "ToDo" })).toBe(null);
		expect(customisationConsequence("get_document", create("Server Script", {}))).toBe(null);
	});

	it("is what the write consequence says for a customisation", () => {
		expect(writeConsequence("create_document", create("Custom Field", { dt: "Item" }))).toBe("Adds a field to every Item");
	});
});

describe("customisationConsequence on partial updates", () => {
	const update = (doctype, data) => customisationConsequence("update_document", { doctype, name: "X", data });

	it("says nothing when the field that drives the sentence is missing", () => {
		expect(update("Server Script", { script: "x" })).toBe(null);
		expect(update("Server Script", { script_type: "DocType Event" })).toBe(null);
		expect(update("Client Script", { script: "x" })).toBe(null);
		expect(update("Custom Field", { label: "x" })).toBe(null);
		expect(update("Property Setter", { value: "1" })).toBe(null);
		expect(update("Workflow", { is_active: 1 })).toBe(null);
		expect(update("Print Format", { html: "x" })).toBe(null);
		expect(update("Notification", { subject: "x" })).toBe(null);
		expect(update("Report", { query: "x" })).toBe(null);
	});

	it("falls back to the generic update line on the card", () => {
		expect(writeConsequence("update_document", { doctype: "Server Script", name: "X", data: { script: "x" } })).toBe(
			"This will modify an existing record in your ERP",
		);
	});

	it("still describes an update that restates the driving fields", () => {
		expect(update("Server Script", { reference_doctype: "Item", doctype_event: "Before Save" })).toBe(
			"This code will run every time someone saves an Item",
		);
	});
});

describe("connection-prefixed tool names", () => {
	it("match the plain tool", () => {
		const input = { doctype: "Custom Field", data: { dt: "Item" } };
		expect(customisationConsequence("prod_create_document", input)).toBe("Adds a field to every Item");
		expect(customisationConsequence("prod_delete_document", { doctype: "Role" })).toBe(
			"This removes a customisation from your site for everyone",
		);
		expect(writeConsequence("prod_document_action", { action: "cancel" })).toContain("cancel a submitted record");
		expect(customisationConsequence("my_other_tool", input)).toBe(null);
	});

	it("isCustomisationRisk reads the first interrupt reason", () => {
		expect(isCustomisationRisk({ interrupts: [{ reason: { risk: "customisation" } }] })).toBe(true);
		expect(isCustomisationRisk({ interrupts: [{ reason: { risk: "other" } }] })).toBe(false);
		expect(isCustomisationRisk({})).toBe(false);
		expect(isCustomisationRisk(null)).toBe(false);
	});
});
