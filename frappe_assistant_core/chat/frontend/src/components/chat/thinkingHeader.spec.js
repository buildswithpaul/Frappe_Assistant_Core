import { describe, it, expect } from "vitest";
import { thinkingHeaderHtml } from "./thinkingHeader";

describe("thinkingHeaderHtml", () => {
	it("drops the bold wrapper of a reasoning-summary title", () => {
		expect(thinkingHeaderHtml("**Assessing sales orders**\n\nI need to count them.")).toBe(
			"Assessing sales orders"
		);
	});

	it("drops other whole-line wrappers and heading markers", () => {
		expect(thinkingHeaderHtml("__Planning the query__")).toBe("Planning the query");
		expect(thinkingHeaderHtml("*Checking totals*")).toBe("Checking totals");
		expect(thinkingHeaderHtml("## Reading the doctype")).toBe("Reading the doctype");
	});

	it("renders inline markdown inside the line", () => {
		expect(thinkingHeaderHtml("Checking `Sales Order` for **draft** rows")).toBe(
			"Checking <code>Sales Order</code> for <strong>draft</strong> rows"
		);
	});

	it("keeps two separate bold spans as markdown, not one wrapper", () => {
		expect(thinkingHeaderHtml("**Sales** vs **Purchase**")).toBe(
			"<strong>Sales</strong> vs <strong>Purchase</strong>"
		);
	});

	it("never renders links or raw HTML in the header button", () => {
		expect(thinkingHeaderHtml("See [docs](https://example.com)")).toBe("See docs");
		expect(thinkingHeaderHtml('<img src=x onerror="alert(1)">Hi')).toBe("Hi");
	});

	it("shortens a long line as plain text without stray markers", () => {
		const long = `**Bold start** ${"word ".repeat(30)}`;
		const html = thinkingHeaderHtml(long);
		expect(html.endsWith("...")).toBe(true);
		expect(html).not.toContain("*");
		expect(html.length).toBeLessThanOrEqual(103);
	});

	it("falls back when there is no content", () => {
		expect(thinkingHeaderHtml("")).toBe("Thought about the request");
		expect(thinkingHeaderHtml("****")).toBe("Thought about the request");
	});
});
