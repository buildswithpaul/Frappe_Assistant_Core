import { describe, it, expect } from "vitest";
import { categoriesFrom, sameTemplateSet } from "./marketplaceFacets";

describe("sameTemplateSet", () => {
	it("is true for the same templates in any order", () => {
		expect(sameTemplateSet([{ name: "a" }, { name: "b" }], [{ name: "b" }, { name: "a" }])).toBe(true);
	});

	it("is false when one list has more", () => {
		expect(sameTemplateSet([{ name: "a" }], [{ name: "a" }, { name: "b" }])).toBe(false);
		expect(sameTemplateSet([], [])).toBe(false);
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
