import { afterEach, describe, expect, it } from "vitest";

import { makeBlocks } from "./pageBlocks";
import { fakeFrappe } from "./__tests__/pageBlocksFake";

const SAVE = "frappe.client.save";
const SET_VALUE = "frappe.client.set_value";

const RISKS = [
	{ fieldname: "severity", label: "Severity", fieldtype: "Select", options: ["HIGH", "MED", "LOW"], badge: true },
	{ fieldname: "description", label: "Description", fieldtype: "Small Text" },
];
const update = {
	doctype: "BU Update",
	name: "BU-0001",
	title: "Decathlon",
	notes: "Two freshers started",
	modified_by: "avery@example.com",
	modified: "2026-11-13 10:00:00",
	risks: [{ name: "r1", severity: "HIGH", description: "Slow conversion", owner_note: "kept" }],
};

let el;
afterEach(() => el?.remove());
const mount = () => {
	el = document.createElement("div");
	document.body.append(el);
	return el;
};
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const button = (root, text) => [...root.querySelectorAll("button")].find((b) => b.textContent === text);

describe("editList", () => {
	it("lists the rows, with a severity badge", async () => {
		const root = mount();
		await makeBlocks(fakeFrappe({ docs: [update] })).editList(root, { doctype: "BU Update", name: "BU-0001", table: "risks", columns: RISKS, canEdit: false });
		const rows = root.querySelectorAll("ul.mk-list > li");
		expect(rows).toHaveLength(1);
		expect(rows[0].querySelector(".mk-badge").className).toContain("mk-sev-high");
		expect(rows[0].textContent).toContain("Slow conversion");
		expect(root.querySelector(".mk-edit")).toBeNull();
	});

	it("shows an unknown severity as a plain badge", async () => {
		const root = mount();
		const doc = { ...update, risks: [{ name: "r1", severity: "URGENT", description: "x" }] };
		await makeBlocks(fakeFrappe({ docs: [doc] })).editList(root, { doctype: "BU Update", name: "BU-0001", table: "risks", columns: RISKS, canEdit: false });
		expect(root.querySelector(".mk-badge").className).toBe("mk-badge");
	});

	it("sets a row's value as text, never as html", async () => {
		const root = mount();
		const doc = { ...update, risks: [{ name: "r1", severity: "LOW", description: '<img src=x onerror="alert(1)">' }] };
		await makeBlocks(fakeFrappe({ docs: [doc] })).editList(root, { doctype: "BU Update", name: "BU-0001", table: "risks", columns: RISKS, canEdit: true });
		expect(root.querySelector("img")).toBeNull();
		button(root, "Edit").click();
		expect(root.querySelector("img")).toBeNull();
		expect(root.querySelector("textarea").value).toBe('<img src=x onerror="alert(1)">');
	});

	it("says so when there are no rows", async () => {
		const root = mount();
		await makeBlocks(fakeFrappe({ docs: [{ ...update, risks: [] }] })).editList(root, { doctype: "BU Update", name: "BU-0001", table: "risks", columns: RISKS, canEdit: false, emptyText: "No risks" });
		expect(root.textContent).toContain("No risks");
	});

	it("asks whether the viewer may edit when the page does not say", async () => {
		const root = mount();
		const f = fakeFrappe({ docs: [update], answers: { "frappe.client.has_permission": { has_permission: false } } });
		await makeBlocks(f).editList(root, { doctype: "BU Update", name: "BU-0001", table: "risks", columns: RISKS });
		expect(root.querySelector(".mk-edit")).toBeNull();
	});

	it("saves the edited and added rows onto the record as it is now, keeping fields it does not show", async () => {
		const root = mount();
		// Someone else renamed the record after the page read it; the save must not undo that.
		const now = { ...update, title: "Decathlon India" };
		const f = fakeFrappe({ docs: [update, now], answers: { [SAVE]: (args) => args.doc } });
		await makeBlocks(f).editList(root, { doctype: "BU Update", name: "BU-0001", table: "risks", columns: RISKS, canEdit: true });
		button(root, "Edit").click();
		root.querySelector("textarea").value = "Slow conversion this quarter";
		button(root, "Add row").click();
		const rows = root.querySelectorAll(".mk-edit-row");
		rows[1].querySelector("select").value = "MED";
		rows[1].querySelector("textarea").value = "Content development";
		button(root, "Add row").click();
		button(root, "Save").click();
		await settle();
		const save = f.calls.find((c) => c.method === SAVE);
		expect(save.args.doc.title).toBe("Decathlon India");
		expect(save.args.doc.risks).toEqual([
			{ name: "r1", severity: "HIGH", description: "Slow conversion this quarter", owner_note: "kept" },
			{ severity: "MED", description: "Content development" },
		]);
		expect(root.querySelector("ul.mk-list").textContent).toContain("Content development");
	});

	it("drops a removed row", async () => {
		const root = mount();
		const f = fakeFrappe({ docs: [update], answers: { [SAVE]: (args) => args.doc } });
		await makeBlocks(f).editList(root, { doctype: "BU Update", name: "BU-0001", table: "risks", columns: RISKS, canEdit: true });
		button(root, "Edit").click();
		button(root, "Remove").click();
		button(root, "Save").click();
		await settle();
		expect(f.calls.find((c) => c.method === SAVE).args.doc.risks).toEqual([]);
	});

	it("keeps what the user typed and says why when the save is refused", async () => {
		const root = mount();
		const refused = Object.assign(new Error("Not permitted"), { status: 403 });
		const f = fakeFrappe({ docs: [update], answers: { [SAVE]: refused } });
		await makeBlocks(f).editList(root, { doctype: "BU Update", name: "BU-0001", table: "risks", columns: RISKS, canEdit: true });
		button(root, "Edit").click();
		root.querySelector("textarea").value = "Typed by the user";
		button(root, "Save").click();
		await settle();
		expect(root.querySelector("textarea").value).toBe("Typed by the user");
		expect(root.querySelector("p.mk-edit-error").textContent).toBe("Not permitted");
	});

	it("saves nothing on Cancel", async () => {
		const root = mount();
		const f = fakeFrappe({ docs: [update] });
		await makeBlocks(f).editList(root, { doctype: "BU Update", name: "BU-0001", table: "risks", columns: RISKS, canEdit: true });
		button(root, "Edit").click();
		button(root, "Cancel").click();
		expect(f.calls.some((c) => c.method === SAVE)).toBe(false);
		expect(root.querySelector("ul.mk-list")).not.toBeNull();
	});
});

describe("editText", () => {
	it("shows the field and saves an edit with set_value", async () => {
		const root = mount();
		const f = fakeFrappe({ docs: [update], answers: { [SET_VALUE]: (args) => ({ ...update, notes: args.value }) } });
		await makeBlocks(f).editText(root, { doctype: "BU Update", name: "BU-0001", fieldname: "notes", multiline: true, canEdit: true });
		expect(root.querySelector(".mk-text").textContent).toBe("Two freshers started");
		button(root, "Edit").click();
		root.querySelector("textarea").value = "Three freshers started";
		button(root, "Save").click();
		await settle();
		expect(f.calls.find((c) => c.method === SET_VALUE).args).toEqual({ doctype: "BU Update", name: "BU-0001", fieldname: "notes", value: "Three freshers started" });
		expect(root.querySelector(".mk-text").textContent).toBe("Three freshers started");
	});

	it("keeps the input when the save fails", async () => {
		const root = mount();
		const f = fakeFrappe({ docs: [update], answers: { [SET_VALUE]: new Error("Validation failed") } });
		await makeBlocks(f).editText(root, { doctype: "BU Update", name: "BU-0001", fieldname: "notes", canEdit: true });
		button(root, "Edit").click();
		root.querySelector("input").value = "Edited";
		button(root, "Save").click();
		await settle();
		expect(root.querySelector("input").value).toBe("Edited");
		expect(root.querySelector("p.mk-edit-error").textContent).toBe("Validation failed");
	});
});
