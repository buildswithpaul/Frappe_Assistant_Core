import { describe, expect, it } from "vitest";
import { EXPLAINED_POWERS, explainContent, questionFor } from "./powerExplain";

describe("powerExplain", () => {
	it("Ask and Pages explain first; the others go straight to their page", () => {
		expect(EXPLAINED_POWERS).toEqual(["ask", "pages"]);
		for (const id of ["setup", "templates", "knowledge", "agents"]) expect(explainContent(id)).toBeNull();
	});

	it("each card says what the power is, gives examples, and offers to do it", () => {
		const ask = explainContent("ask");
		expect(ask).toMatchObject({ power: "ask", title: "Ask your data in plain words", primary: { label: "Ask one for me" } });
		expect(ask.highlights).toHaveLength(3);
		const pages = explainContent("pages");
		expect(pages).toMatchObject({ power: "pages", title: "Pages: live reports from any answer" });
		expect(pages.body).toContain("save the answer as a Page");
		expect(pages.media).toEqual({ art: "feature", feature: "pages" });
	});

	it("Ask asks the user's own first Home starter, skipping page asks; a fixed question when there is none", () => {
		const suggestions = [
			{ source: "page", description: "Summarise this invoice" },
			{ source: "curated", description: "Which items are below reorder level?" },
		];
		expect(questionFor("ask", suggestions)).toBe("Which items are below reorder level?");
		expect(questionFor("ask", [])).toBe("Who are my top 5 customers by sales this year?");
	});

	it("Pages asks for numbers and to save them as a Page", () => {
		expect(questionFor("pages")).toBe("Show this month's sales by customer and save it as a Page.");
	});
});
