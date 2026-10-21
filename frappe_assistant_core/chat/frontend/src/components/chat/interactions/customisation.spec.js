import { describe, it, expect } from "vitest";
import { isCustomisationRisk } from "@/utils/toolNames";
import {
	conditionNotice,
	customisationConsequence,
	fieldPlacementTarget,
	renameNotice,
	renameKeys,
	writesCondition,
	writeConsequence,
} from "./customisation";

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
		for (const dt of ["Role", "Custom DocPerm"]) {
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

	it("falls back to a doctype-level sentence when the driving field is missing", () => {
		expect(update("Server Script", { script: "x" })).toBe("Changes server code that runs on this site");
		expect(update("Server Script", { script_type: "DocType Event" })).toBe("Changes server code that runs on this site");
		expect(update("Client Script", { script: "x" })).toBe("Changes how a form behaves in Desk for everyone");
		expect(update("Custom Field", { label: "x" })).toBe("Changes a field on a form for everyone");
		expect(update("Property Setter", { value: "1" })).toBe("Changes how a field behaves for everyone");
		expect(update("Workflow", { is_active: 1 })).toBe("Changes how records are approved for everyone");
		expect(update("Print Format", { html: "x" })).toBe("Changes how a document prints");
		expect(update("Notification", { subject: "x" })).toBe("Changes messages that are sent automatically when records change");
		expect(update("Report", { query: "x" })).toBe("Changes a report");
	});

	it("never shows the generic ERP line for a customisation update", () => {
		expect(writeConsequence("update_document", { doctype: "Server Script", name: "X", data: { script: "x" } })).toBe(
			"Changes server code that runs on this site",
		);
	});

	it("still describes an update that restates the driving fields", () => {
		expect(update("Server Script", { reference_doctype: "Item", doctype_event: "Before Save" })).toBe(
			"This code will run every time someone saves an Item",
		);
	});
});

describe("customisationConsequence for every customisation doctype", () => {
	const DOCTYPES = [
		["Server Script", { script_type: "DocType Event", reference_doctype: "Lead", doctype_event: "Before Save" }, "This code will run every time someone saves a Lead", "This code will run every time someone saves a Lead"],
		["Client Script", { dt: "Lead" }, "This changes how the Lead form behaves in Desk for everyone", "This changes how the Lead form behaves in Desk for everyone"],
		["Custom Field", { dt: "Lead" }, "Adds a field to every Lead", "Changes a field on every Lead"],
		["Property Setter", { doc_type: "Lead" }, "Changes how a Lead field behaves for everyone", "Changes how a Lead field behaves for everyone"],
		["Workflow", { document_type: "Lead" }, "Changes how Lead records are approved for everyone", "Changes how Lead records are approved for everyone"],
		["Workflow State", {}, "Changes how records are approved for everyone", "Changes how records are approved for everyone"],
		["Workflow Action Master", {}, "Changes how records are approved for everyone", "Changes how records are approved for everyone"],
		["Custom DocPerm", {}, "Changes who can see or do what on this site", "Changes who can see or do what on this site"],
		["DocType", {}, "Changes how a kind of record is built for everyone", "Changes how a kind of record is built for everyone"],
		["Role", {}, "Changes who can see or do what on this site", "Changes who can see or do what on this site"],
		["Report", { ref_doctype: "Lead" }, "Adds a report on Lead", "Changes a report on Lead"],
		["Print Format", { doc_type: "Lead" }, "Changes how Lead prints", "Changes how Lead prints"],
		["Notification", { document_type: "Lead" }, "Sends messages automatically when Lead records change", "Sends messages automatically when Lead records change"],
	];

	it.each(DOCTYPES)("%s: create and update each have their own sentence", (doctype, data, created, updated) => {
		expect(customisationConsequence("create_document", { doctype, data })).toBe(created);
		expect(customisationConsequence("update_document", { doctype, name: "X", data })).toBe(updated);
	});

	it.each(DOCTYPES)("%s: an update with no fields never falls to the generic line", (doctype) => {
		const text = writeConsequence("update_document", { doctype, name: "X", data: {} });
		expect(text).not.toMatch(/your ERP/);
		expect(text).not.toBe("");
	});

	it("keeps Workflow State a sentence even though its record carries no doctype", () => {
		expect(writeConsequence("create_document", { doctype: "Workflow State", data: { workflow_state_name: "Pending" } })).toBe(
			"Changes how records are approved for everyone",
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

const NOTICE = "Checked in the Desk form only — imports, the API and FACO's own writes are not checked.";

describe("conditionNotice", () => {
	it("applies to a Custom Field create that sets a condition", () => {
		const input = { doctype: "Custom Field", data: { dt: "Sales Order", depends_on: "eval:doc.qty > 1" } };
		expect(conditionNotice("create_document", input)).toBe(NOTICE);
	});

	it("applies to a Custom Field update that sets a condition", () => {
		const input = { doctype: "Custom Field", name: "Sales Order-x", data: { mandatory_depends_on: "eval:doc.qty" } };
		expect(conditionNotice("update_document", input)).toBe(NOTICE);
	});

	it("applies to a Property Setter whose property is a condition", () => {
		const input = { doctype: "Property Setter", data: { property: "read_only_depends_on", value: "eval:doc.qty" } };
		expect(conditionNotice("create_document", input)).toBe(NOTICE);
	});

	it("stays quiet for everything else", () => {
		const other = { doctype: "Property Setter", data: { property: "hidden", value: "1" } };
		expect(conditionNotice("create_document", other)).toBeNull();
		expect(conditionNotice("create_document", { doctype: "Custom Field", data: { label: "PO" } })).toBeNull();
		expect(conditionNotice("create_document", { doctype: "Custom Field", data: { depends_on: "" } })).toBeNull();
		expect(conditionNotice("delete_document", { doctype: "Custom Field", name: "x" })).toBeNull();
		expect(conditionNotice("create_document", { doctype: "ToDo", data: { depends_on: "eval:1" } })).toBeNull();
	});

	it("finds a condition value the notice is about", () => {
		const input = { doctype: "Property Setter", data: { property: "depends_on", value: "eval:doc.qty" } };
		expect(writesCondition("create_document", input, "value")).toBe(true);
		expect(writesCondition("create_document", input, "property")).toBe(false);
	});
});

describe("fieldPlacementTarget", () => {
	it("reads dt, insert_after and fieldtype from a Custom Field create", () => {
		const input = { doctype: "Custom Field", data: { dt: "Customer", insert_after: "email_id", fieldtype: "Data" } };
		expect(fieldPlacementTarget("create_document", input)).toEqual({
			doctype: "Customer",
			insertAfter: "email_id",
			fieldtype: "Data",
		});
	});

	it("is null for an update without dt, another doctype, or another tool", () => {
		expect(fieldPlacementTarget("update_document", { doctype: "Custom Field", name: "x", data: { label: "y" } })).toBeNull();
		expect(fieldPlacementTarget("create_document", { doctype: "ToDo", data: { dt: "Customer" } })).toBeNull();
		expect(fieldPlacementTarget("delete_document", { doctype: "Custom Field", data: { dt: "Customer" } })).toBeNull();
	});

	it("needs insert_after on an update, so a condition-only change makes no claim about placement", () => {
		const bare = { doctype: "Custom Field", name: "x", data: { dt: "Customer", depends_on: "eval:doc.qty" } };
		expect(fieldPlacementTarget("update_document", bare)).toBeNull();
		const moved = { doctype: "Custom Field", name: "x", data: { dt: "Customer", insert_after: "email_id" } };
		expect(fieldPlacementTarget("update_document", moved)).toMatchObject({ doctype: "Customer", insertAfter: "email_id" });
	});

	it("follows a prefixed tool name", () => {
		const input = { doctype: "Custom Field", data: { dt: "Customer" } };
		expect(fieldPlacementTarget("prod_create_document", input)).toMatchObject({ doctype: "Customer" });
	});
});

describe("renameNotice", () => {
	it("treats a number or true as a rename value, and null, false or blank as none", () => {
		const update = (data) => ({ doctype: "Role", name: "A", data });
		expect(renameNotice("update_document", update({ disabled: 1, new_name: 42 }))).not.toBeNull();
		expect(renameNotice("update_document", update({ disabled: 1, rename: true }))).not.toBeNull();
		for (const blank of [null, false, "", "  "]) {
			expect(renameNotice("update_document", update({ disabled: 1, new_name: blank }))).toBeNull();
		}
	});

	it("does not call a restated name a rename when only its type differs", () => {
		const asNumber = { doctype: "ToDo", name: "5", data: { status: "Closed", name: 5 } };
		const asString = { doctype: "ToDo", name: 5, data: { status: "Closed", name: "5" } };
		expect(renameNotice("update_document", asNumber)).toBeNull();
		expect(renameNotice("update_document", asString)).toBeNull();
		expect(renameKeys("update_document", asString)).toEqual([]);
	});

	it("explains a rename on an update and names the keys to hide", () => {
		const input = { doctype: "Role", name: "A", data: { name: "B", disabled: 1 } };
		expect(renameNotice("update_document", input)).toBe("Renaming isn't possible here. Only the other changes will be saved.");
		expect(renameKeys("update_document", input)).toEqual(["new_name", "rename"]);
	});

	it("is null for a create, a plain update and a restated name", () => {
		expect(renameNotice("create_document", { doctype: "Role", data: { name: "B" } })).toBeNull();
		expect(renameNotice("update_document", { doctype: "Role", name: "A", data: { disabled: 1 } })).toBeNull();
		expect(renameNotice("update_document", { doctype: "Role", name: "A", data: { name: "A" } })).toBeNull();
		expect(renameKeys("update_document", { doctype: "Role", name: "A", data: {} })).toEqual([]);
	});
});
