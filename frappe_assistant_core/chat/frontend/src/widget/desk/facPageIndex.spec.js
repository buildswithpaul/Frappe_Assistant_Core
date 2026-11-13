import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

// The Desk page inlines these plain scripts with Frappe's render_include, so the test loads them the same
// way: as source text, evaluated together for the functions they declare, with Desk's global __.
const DIR = resolve(import.meta.dirname, "../../../../../assistant_core/page/fac_pages");
const SOURCE = ["fac_page_draft.js", "fac_page_card.js", "fac_page_index.js"]
	.map((file) => readFileSync(resolve(DIR, file), "utf-8"))
	.join("\n");
const translate = (text, args = []) => args.reduce((out, arg, i) => out.replace(`{${i}}`, arg), text);
const fac_page_index = new Function("__", `${SOURCE}\nreturn fac_page_index;`)(translate);

const personal = {
	name: "my-receivables",
	title: "My Receivables",
	description: "Overdue invoices by customer",
	visibility: "Only me",
	draft: false,
	modified: "2026-10-27 10:00:00",
	roles: [],
	can_manage: true,
	can_share: false,
	preview_html: null,
};
const shared = {
	name: "quick-customer",
	title: "Quick Customer",
	description: "",
	visibility: "Shared",
	draft: false,
	modified: "2026-10-27 09:00:00",
	roles: ["Sales User"],
	can_manage: false,
	can_share: false,
	preview_html: null,
};
const draft = { ...shared, name: "bu-margin", title: "BU Margin", draft: true, can_manage: true };

const render = (options) =>
	fac_page_index({
		href: (name) => `/app/fac-pages/${name}`,
		updated: () => "2 hours ago",
		kit_css: "",
		...options,
	});
const texts = (root, selector) => [...root.querySelectorAll(selector)].map((el) => el.textContent);
const visibleTitles = (root) =>
	[...root.querySelectorAll(".fac-page-index-card")]
		.filter((card) => !card.hidden)
		.map((card) => card.querySelector(".fac-page-index-title").textContent);

describe("fac_page_index", () => {
	it("lists every page as a card, the user's own first", () => {
		const root = render({ pages: [shared, personal] });
		expect(visibleTitles(root)).toEqual(["My Receivables", "Quick Customer"]);
	});

	it("counts each filter, and shows Drafts only when there are drafts", () => {
		expect(texts(render({ pages: [shared, personal] }), ".fac-page-index-chip")).toEqual(["All 2", "Mine 1", "Shared 1"]);
		expect(texts(render({ pages: [shared, personal, draft] }), ".fac-page-index-chip")).toEqual([
			"All 3",
			"Mine 1",
			"Shared 1",
			"Drafts 1",
		]);
	});

	it("filters the cards by the chip clicked and marks it active", () => {
		const root = render({ pages: [shared, personal, draft] });
		const drafts = [...root.querySelectorAll(".fac-page-index-chip")].find((chip) => chip.textContent === "Drafts 1");
		drafts.click();
		expect(visibleTitles(root)).toEqual(["BU Margin"]);
		expect(drafts.classList.contains("active")).toBe(true);
	});

	it("searches titles and descriptions as the user types", () => {
		const root = render({ pages: [shared, personal] });
		const search = root.querySelector("input.fac-page-index-search");
		search.value = "OVERDUE";
		search.dispatchEvent(new Event("input"));
		expect(visibleTitles(root)).toEqual(["My Receivables"]);
	});

	it("says no page matches a search, and keeps the filters", () => {
		const root = render({ pages: [shared, personal] });
		const search = root.querySelector("input.fac-page-index-search");
		search.value = "payroll";
		search.dispatchEvent(new Event("input"));
		const nomatch = root.querySelector(".fac-page-index-nomatch");
		expect(nomatch.hidden).toBe(false);
		expect(nomatch.textContent).toBe("No pages match “payroll”");
		expect(root.querySelectorAll(".fac-page-index-chip")).toHaveLength(3);
		expect(root.querySelector(".fac-page-index-empty")).toBeNull();
	});

	it("says so when there are no pages, and offers a new page to those who can chat", () => {
		const new_page = vi.fn();
		const root = render({ pages: [], can_chat: true, actions: { new_page } });
		expect(texts(root, ".fac-page-index-empty")).toEqual(["No pages have been shared with you yet."]);
		root.querySelector(".fac-page-index-new").click();
		expect(new_page).toHaveBeenCalled();
	});

	it("ends the grid with a New page tile only for those who can chat", () => {
		const actions = { new_page: vi.fn() };
		expect(render({ pages: [shared], actions }).querySelector(".fac-page-index-new")).toBeNull();
		const grid = render({ pages: [shared], can_chat: true, actions }).querySelector(".fac-page-index-list");
		expect(grid.lastElementChild.classList.contains("fac-page-index-new")).toBe(true);
	});

	it("sets a search term as text in the no-match line", () => {
		const root = render({ pages: [shared] });
		const search = root.querySelector("input.fac-page-index-search");
		search.value = "<img src=x onerror=alert(1)>";
		search.dispatchEvent(new Event("input"));
		expect(root.querySelector(".fac-page-index-nomatch img")).toBeNull();
	});
});
