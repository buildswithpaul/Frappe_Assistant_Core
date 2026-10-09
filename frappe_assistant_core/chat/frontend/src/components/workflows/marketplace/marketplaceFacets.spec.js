import { describe, it, expect } from "vitest";
import { categoriesFrom, hasFeaturedSubset } from "./marketplaceFacets";

describe("hasFeaturedSubset", () => {
	it("is false when every template is featured", () => {
		const all = Array.from({ length: 8 }, (_, i) => ({ name: `t${i}`, featured: true }));
		expect(hasFeaturedSubset(all)).toBe(false);
	});

	it("is false when no template is featured", () => {
		expect(hasFeaturedSubset([{ name: "a", featured: false }])).toBe(false);
		expect(hasFeaturedSubset([])).toBe(false);
	});

	it("is true when some but not all templates are featured", () => {
		const all = Array.from({ length: 24 }, (_, i) => ({ name: `t${i}`, featured: i < 9 }));
		expect(hasFeaturedSubset(all)).toBe(true);
	});
});

describe("categoriesFrom", () => {
	it("lists only categories that have templates", () => {
		const t = [{ category: "Finance" }, { category: "HR" }, { category: "Finance" }, { category: "" }];
		expect(categoriesFrom(t, null)).toEqual(["Finance", "HR"]);
	});

	it("keeps the selected category visible", () => {
		expect(categoriesFrom([{ category: "Finance" }], "Sales")).toEqual(["Finance", "Sales"]);
	});
});
