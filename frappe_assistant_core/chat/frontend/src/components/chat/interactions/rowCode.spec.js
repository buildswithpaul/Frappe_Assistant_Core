import { describe, it, expect } from "vitest";
import { rowCodeCells, rowsWithoutCode } from "./rowCode";

const OPEN = "eval:doc.status == 'Open'";
const cellsOf = (cells) => cells.map((c) => [c.key, c.code, c.previous]);

describe("rowCodeCells", () => {
	it("lists each non-blank code cell of the doctype's code tables", () => {
		const fields = {
			transitions: [{ state: "A", condition: "doc.x" }, { state: "B", condition: "  " }],
			states: [{ state: "A", condition: "ignored" }],
		};
		expect(rowCodeCells("Workflow", fields).map((c) => [c.key, c.code])).toEqual([["transitions.0.condition", "doc.x"]]);
		expect(rowCodeCells("Web Form", fields)).toEqual([]);
		expect(rowCodeCells("Workflow", { transitions: "x" })).toEqual([]);
	});

	it("diffs a named row against the stored row of that name", () => {
		const current = {
			transitions: [
				{ name: "r1", state: "A", action: "Go", next_state: "B", condition: "doc.a" },
				{ name: "r2", state: "B", action: "Go", next_state: "A", condition: "doc.b" },
			],
		};
		const fields = { transitions: [{ name: "r2", condition: "doc.c" }] };
		expect(cellsOf(rowCodeCells("Workflow", fields, current))).toEqual([["transitions.0.condition", "doc.c", "doc.b"]]);
	});

	it("diffs a replace-mode row against the stored row with the same key columns", () => {
		const current = {
			recipients: [
				{ name: "x", receiver_by_role: "Sales User", receiver_by_document_field: "", condition: "", cc: "a@x.com", bcc: "" },
				{ name: "y", receiver_by_role: "Accounts User", receiver_by_document_field: "", condition: "", cc: "{{ doc.owner }}", bcc: "" },
			],
		};
		const fields = { recipients: [{ receiver_by_role: "Accounts User", cc: "{{ doc.modified_by }}" }] };
		expect(cellsOf(rowCodeCells("Notification", fields, current))).toEqual([
			["recipients.0.cc", "{{ doc.modified_by }}", "{{ doc.owner }}"],
		]);
	});

	it("diffs a new row as all added, and shows code alone when nothing was fetched", () => {
		const fields = { transitions: [{ state: "C", action: "Go", next_state: "A", condition: "doc.d" }] };
		expect(cellsOf(rowCodeCells("Workflow", fields, { transitions: [] }))).toEqual([["transitions.0.condition", "doc.d", ""]]);
		expect(cellsOf(rowCodeCells("Workflow", fields, null))).toEqual([["transitions.0.condition", "doc.d", null]]);
	});

	it("shows a DocType field's eval: condition and HTML markup, not a bare fieldname or a Data field's options", () => {
		const fields = {
			fields: [
				{ fieldname: "notes", fieldtype: "Data", depends_on: OPEN, options: "Email" },
				{ fieldname: "summary", fieldtype: "Data", depends_on: "status" },
				{ fieldname: "banner", fieldtype: "HTML", options: "<b>{{ doc.status }}</b>" },
			],
		};
		const cells = rowCodeCells("DocType", fields);
		expect(cells.map((c) => [c.key, c.language])).toEqual([
			["fields.0.depends_on", "javascript"],
			["fields.2.options", "xml"],
		]);
	});

	it("diffs a DocType field's code by fieldname, including a cleared condition and a patch row's stored type", () => {
		const current = {
			fields: [
				{ name: "f1", fieldname: "notes", fieldtype: "Data", depends_on: OPEN, mandatory_depends_on: "", read_only_depends_on: "", options: "" },
				{ name: "f2", fieldname: "banner", fieldtype: "HTML", depends_on: "", mandatory_depends_on: "", read_only_depends_on: "", options: "<b>old</b>" },
			],
		};
		const replaced = { fields: [{ fieldname: "notes", fieldtype: "Data", depends_on: "" }] };
		expect(cellsOf(rowCodeCells("DocType", replaced, current))).toEqual([["fields.0.depends_on", "", OPEN]]);
		const patched = { fields: [{ name: "f2", options: "<b>new</b>" }] };
		expect(cellsOf(rowCodeCells("DocType", patched, current))).toEqual([["fields.0.options", "<b>new</b>", "<b>old</b>"]]);
	});
});

describe("rowsWithoutCode", () => {
	it("leaves out the cells shown as code and blank code cells, and keeps the rest", () => {
		const rows = [
			{ fieldname: "notes", fieldtype: "Data", depends_on: OPEN, read_only_depends_on: "" },
			{ fieldname: "summary", fieldtype: "Data", depends_on: "status" },
		];
		const cells = rowCodeCells("DocType", { fields: rows });
		expect(rowsWithoutCode("DocType", "fields", rows, cells)).toEqual([
			{ fieldname: "notes", fieldtype: "Data" },
			{ fieldname: "summary", fieldtype: "Data", depends_on: "status" },
		]);
		expect(rowsWithoutCode("Web Form", "fields", rows, cells)).toBe(rows);
	});
});
