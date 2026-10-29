import { describe, it, expect } from "vitest";
import { openingCodeBlocks, openingTarget } from "./openingCode";

describe("openingTarget", () => {
	it("asks about a DocType update that sets permissions or makes it a child table", () => {
		const perms = { doctype: "DocType", name: "Site Visit", data: { permissions: [{ role: "Employee" }] } };
		expect(openingTarget("update_document", perms)).toEqual({ target: "Site Visit" });
		expect(openingTarget("prod_update_document", { ...perms, data: { istable: 1 } })).toEqual({ target: "Site Visit" });
		expect(openingTarget("update_document", { ...perms, data: { description: "x" } })).toBeNull();
		expect(openingTarget("create_document", { doctype: "DocType", data: { name: "New" } })).toBeNull();
	});

	it("asks about a Custom DocPerm write by its parent, or by its name when the parent is left out", () => {
		const create = { doctype: "Custom DocPerm", data: { parent: "Site Visit", role: "Employee" } };
		expect(openingTarget("create_document", create)).toEqual({ target: "Site Visit" });
		expect(openingTarget("update_document", { doctype: "Custom DocPerm", name: "p1", data: { role: "Employee" } })).toEqual({
			customDocperm: "p1",
		});
		expect(openingTarget("delete_document", { doctype: "Custom DocPerm", name: "p1" })).toBeNull();
		expect(openingTarget("update_document", { doctype: "Custom Field", name: "x", data: {} })).toBeNull();
	});

	it("asks about a Property Setter that makes the DocType a child table, Single or virtual", () => {
		const setter = { doctype: "Property Setter", data: { doc_type: "Site Visit", doctype_or_field: "DocType", property: "istable", value: "1" } };
		expect(openingTarget("create_document", setter)).toEqual({ target: "Site Visit" });
		expect(openingTarget("create_document", { ...setter, data: { ...setter.data, property: "label" } })).toBeNull();
	});
});

describe("openingCodeBlocks", () => {
	it("labels each entry with the record that sets it and highlights it by kind", () => {
		const blocks = openingCodeBlocks([
			{ source: "Custom Field", name: "Site Visit-region", field: "region", key: "depends_on", code: "eval:doc.x" },
			{ source: "Property Setter", name: "ps1", field: "notes", key: "options", code: "<b>x</b>" },
		]);
		expect(blocks.map((b) => [b.label, b.language, b.code])).toEqual([
			["Custom Field region: Depends On", "javascript", "eval:doc.x"],
			["Property Setter notes: Options", "xml", "<b>x</b>"],
		]);
		expect(openingCodeBlocks(null)).toEqual([]);
	});
});
