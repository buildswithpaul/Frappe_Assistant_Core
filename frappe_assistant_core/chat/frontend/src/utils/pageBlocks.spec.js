import { describe, expect, it } from "vitest";

import { makeBlocks } from "./pageBlocks";
import { fakeFrappe } from "./__tests__/pageBlocksFake";

describe("canWrite", () => {
	it("answers whether the viewer may write the record", async () => {
		const f = fakeFrappe({ answers: { "frappe.client.has_permission": { has_permission: true } } });
		expect(await makeBlocks(f).canWrite("ToDo", "T-1")).toBe(true);
		expect(f.calls[0]).toMatchObject({
			method: "frappe.client.has_permission",
			type: "GET",
			args: { doctype: "ToDo", docname: "T-1", perm_type: "write" },
		});
	});

	it("answers false when the viewer may not", async () => {
		const f = fakeFrappe({ answers: { "frappe.client.has_permission": { has_permission: false } } });
		expect(await makeBlocks(f).canWrite("ToDo", "T-1")).toBe(false);
	});

	it("answers false when the check itself fails", async () => {
		const f = fakeFrappe({ answers: { "frappe.client.has_permission": new Error("offline") } });
		expect(await makeBlocks(f).canWrite("ToDo", "T-1")).toBe(false);
	});
});

describe("updated", () => {
	it("says who changed the record last and when", () => {
		const text = makeBlocks(fakeFrappe()).updated({ modified_by: "avery@example.com", modified: "2026-11-13 10:00:00" });
		expect(text).toBe("Updated by avery@example.com · 13-11-2026");
	});

	it("leaves out what the record does not carry", () => {
		const blocks = makeBlocks(fakeFrappe());
		expect(blocks.updated({ modified_by: "avery@example.com" })).toBe("Updated by avery@example.com");
		expect(blocks.updated({})).toBe("");
	});
});


describe("periodPicker", () => {
	const mountPicker = (options) => {
		const el = document.createElement("div");
		const picker = makeBlocks(fakeFrappe()).periodPicker(el, options);
		return { el, picker, select: el.querySelector("select") };
	};

	it("lists the periods, from plain strings or value and label pairs, with the current one chosen", () => {
		const { el, select } = mountPicker({ options: ["NOV-26 F1", "OCT-26 F2"], value: "OCT-26 F2", label: "Period" });
		expect([...select.options].map((o) => o.value)).toEqual(["NOV-26 F1", "OCT-26 F2"]);
		expect(select.value).toBe("OCT-26 F2");
		expect(el.querySelector(".mk-field.mk-period label").textContent).toBe("Period");
		const pairs = mountPicker({ options: [{ value: "p1", label: "First" }] }).select;
		expect([pairs.options[0].value, pairs.options[0].textContent]).toEqual(["p1", "First"]);
	});

	it("tells the page when the user picks another period", () => {
		const changes = [];
		const { picker, select } = mountPicker({ options: ["A", "B"], value: "A", onChange: (v) => changes.push(v) });
		select.value = "B";
		select.dispatchEvent(new Event("change"));
		expect(changes).toEqual(["B"]);
		expect(picker.value()).toBe("B");
	});

	it("changes the period from the page without reporting it back", () => {
		const changes = [];
		const { picker, select } = mountPicker({ options: ["A", "B"], value: "A", onChange: (v) => changes.push(v) });
		picker.set("B");
		expect(select.value).toBe("B");
		expect(changes).toEqual([]);
	});

	it("sets labels as text, never as html", () => {
		const { el } = mountPicker({ options: [{ value: "x", label: "<b>x</b>" }], label: "<img src=x>" });
		expect(el.querySelector("img")).toBeNull();
		expect(el.querySelector("b")).toBeNull();
	});
});
