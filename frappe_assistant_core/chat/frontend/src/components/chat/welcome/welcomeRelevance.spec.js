import { describe, it, expect } from "vitest";
import { selectWelcomeTiles } from "./welcomeRelevance";

const s = (source, description, name = description) => ({ name, description, source });

describe("selectWelcomeTiles", () => {
	it("fills personalized first (max 3), then pinned, contextual, defaults", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [
				s("default", "d1"), s("default", "d2"), s("default", "d3"), s("default", "d4"),
				s("contextual", "c1"), s("pinned", "p1"),
				s("personalized", "z1"), s("personalized", "z2"), s("personalized", "z3"), s("personalized", "z4"),
			],
			resumePreview: "",
		});
		expect(tiles.map((t) => t.description)).toEqual(["z1", "z2", "z3", "p1"]);
	});

	it("drops suggestions duplicating ANY resume preview", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [
				{ description: "Write the coffee essay", source: "contextual" },
				{ description: "Analyze churn", source: "contextual" },
			],
			resumePreviews: ["Write the coffee essay please", "Something else"],
		});
		expect(tiles.map((t) => t.description)).not.toContain("Write the coffee essay");
	});

	it("accepts legacy resumePreview string", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [{ description: "Write the coffee essay", source: "contextual" }],
			resumePreview: "Write the coffee essay please",
		});
		expect(tiles.map((t) => t.description)).not.toContain("Write the coffee essay");
	});

	it("always returns 4 by backfilling defaults", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [s("pinned", "p1"), s("default", "d1"), s("default", "d2"), s("default", "d3")],
			resumePreview: "",
		});
		expect(tiles).toHaveLength(4);
	});

	it("marks personalized tiles", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [s("personalized", "z1"), s("default", "d1"), s("default", "d2"), s("default", "d3")],
			resumePreview: "",
		});
		expect(tiles[0].personalized).toBe(true);
		expect(tiles[1].personalized).toBe(false);
	});

	it("drops a suggestion that duplicates the resume preview (containment, case-insensitive)", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [
				s("personalized", "Fetch the 10 most recent Sales Invoices"),
				s("default", "d1"), s("default", "d2"), s("default", "d3"), s("default", "d4"),
			],
			resumePreview: "fetch the 10 most recent sales invoices, then read each one…",
		});
		expect(tiles.map((t) => t.description)).toEqual(["d1", "d2", "d3", "d4"]);
	});

	it("dedupes by description across sources", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [
				s("personalized", "Same text"), s("pinned", "same text", "other_name"),
				s("default", "d1"), s("default", "d2"), s("default", "d3"),
			],
			resumePreview: "",
		});
		const descs = tiles.map((t) => t.description.toLowerCase());
		expect(new Set(descs).size).toBe(descs.length);
	});

	it("returns exactly 4 client-side fallback tiles when there are no suggestions at all", () => {
		const tiles = selectWelcomeTiles({ suggestions: [], resumePreview: "" });
		expect(tiles).toHaveLength(4);
		tiles.forEach((t) => {
			expect(t.source).toBe("default");
			expect(t.personalized).toBe(false);
		});
	});

	it("backfills with fallback tiles when only one real suggestion is available", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [s("pinned", "p1")],
			resumePreview: "",
		});
		expect(tiles).toHaveLength(4);
		expect(tiles[0].description).toBe("p1");
		expect(tiles.slice(1).every((t) => t.source === "default")).toBe(true);
	});

	it("skips a fallback tile that duplicates the resume preview and still yields 4", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [s("pinned", "p1"), s("pinned", "p2")],
			resumePreview: "show me my pending tasks and what needs attention today",
		});
		expect(tiles).toHaveLength(4);
		tiles.forEach((t) => {
			const d = t.description.toLowerCase();
			expect(d.includes("show me my pending tasks") || "show me my pending tasks and what needs attention today".includes(d)).toBe(false);
		});
	});

	it("adds no fallback tiles when 4 real suggestions already fill the grid", () => {
		const tiles = selectWelcomeTiles({
			suggestions: [s("default", "d1"), s("default", "d2"), s("default", "d3"), s("default", "d4")],
			resumePreview: "",
		});
		expect(tiles.map((t) => t.description)).toEqual(["d1", "d2", "d3", "d4"]);
	});
});
