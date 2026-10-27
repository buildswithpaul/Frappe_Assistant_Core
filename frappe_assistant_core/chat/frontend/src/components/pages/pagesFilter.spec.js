import { describe, expect, it } from "vitest";

import { countPages, groupPages, matchesFilter, searchPages } from "./pagesFilter";

const page = (name, title, visibility, draft = false) => ({ name, title, visibility, draft });
const pages = [
	page("costs", "Costs by month", "Only me"),
	page("ideas", "Ideas", "Only me"),
	page("sales", "Sales Board", "Shared"),
	page("hiring", "Hiring plan", "Shared", true),
];

describe("groupPages", () => {
	it("puts non-shared pages in mine and shared pages, drafts included, in shared", () => {
		const { mine, shared } = groupPages(pages);
		expect(mine.map((p) => p.name)).toEqual(["costs", "ideas"]);
		expect(shared.map((p) => p.name)).toEqual(["sales", "hiring"]);
	});

	it("keeps the order it was given", () => {
		const { mine } = groupPages([...pages].reverse());
		expect(mine.map((p) => p.name)).toEqual(["ideas", "costs"]);
	});
});

describe("searchPages", () => {
	it("matches the title case-insensitively", () => {
		expect(searchPages(pages, "SALES").map((p) => p.name)).toEqual(["sales"]);
	});

	it("ignores surrounding spaces and returns everything for an empty query", () => {
		expect(searchPages(pages, "  ideas ")).toHaveLength(1);
		expect(searchPages(pages, "   ")).toHaveLength(4);
	});

	it("falls back to the name when a page has no title", () => {
		expect(searchPages([page("untitled-1", "", "Only me")], "untitled")).toHaveLength(1);
	});
});

describe("matchesFilter", () => {
	it("applies each pill", () => {
		const [costs, , sales, hiring] = pages;
		expect([costs, sales, hiring].map((p) => matchesFilter(p, "all"))).toEqual([true, true, true]);
		expect([costs, sales, hiring].map((p) => matchesFilter(p, "mine"))).toEqual([true, false, false]);
		expect([costs, sales, hiring].map((p) => matchesFilter(p, "shared"))).toEqual([false, true, true]);
		expect([costs, sales, hiring].map((p) => matchesFilter(p, "drafts"))).toEqual([false, false, true]);
	});
});

describe("countPages", () => {
	it("counts every pill", () => {
		expect(countPages(pages)).toEqual({ all: 4, mine: 2, shared: 2, drafts: 1 });
	});

	it("reflects the search", () => {
		expect(countPages(searchPages(pages, "plan"))).toEqual({ all: 1, mine: 0, shared: 1, drafts: 1 });
	});
});
