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

	it("Ask picks the user's short Find it starter over a long analysis; See it next; never a page ask", () => {
		const analysis = { source: "curated", description: "Analyze customer relationship data including lead pipeline…" };
		const see = { source: "curated", kind: "see", description: "Top 10 customers by revenue this month" };
		const find = { source: "curated", kind: "find", description: "Who owes us the most, and since when?" };
		const page = { source: "page", kind: "find", description: "Summarise this invoice" };
		expect(questionFor("ask", [analysis, page, see, find])).toBe("Who owes us the most, and since when?");
		expect(questionFor("ask", [analysis, see])).toBe("Top 10 customers by revenue this month");
		expect(questionFor("ask", [analysis])).toBe(analysis.description);
		expect(questionFor("ask", [])).toBe("Who are my top 5 customers by sales this year?");
	});

	it("Pages asks for numbers and to save them as a Page", () => {
		expect(questionFor("pages")).toBe("Show this month's sales by customer and save it as a Page.");
	});
});
