import { describe, expect, it } from "vitest";
import { htmlText } from "./htmlText";

describe("htmlText", () => {
	it("keeps only the text of Frappe's markup", () => {
		expect(htmlText("<b>Not</b>&nbsp;permitted<br>here")).toBe("Not permitted here");
	});

	it("never leaves a tag behind, closed or not", () => {
		expect(htmlText("<b>Denied</b><img src=x onerror=alert(1)//")).toBe("Denied");
		expect(htmlText("<scr<b>ipt>alert(1)</scr</b>ipt>")).not.toMatch(/<\s*script/i);
	});

	it("keeps escaped markup as text rather than turning it into tags", () => {
		expect(htmlText("&lt;b&gt;")).toBe("<b>");
	});

	it("takes anything, not only strings", () => {
		expect(htmlText(undefined)).toBe("");
		expect(htmlText(42)).toBe("42");
	});
});
