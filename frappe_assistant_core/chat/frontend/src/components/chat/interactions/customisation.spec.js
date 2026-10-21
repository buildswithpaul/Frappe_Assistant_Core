import { describe, it, expect } from "vitest";
import { customisationConsequence, writeConsequence } from "./customisation";

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
