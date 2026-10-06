import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// The palette is pastel-on-dark. Other surfaces (ThinkingBlock, document
// preview, ...) render code on a light `pre`, so an unscoped rule would
// make their tokens unreadable.
describe("hljs-theme.css scoping", () => {
	it("scopes every selector under `.text-block pre`", () => {
		const css = readFileSync(
			resolve(__dirname, "../../styles/hljs-theme.css"),
			"utf8"
		).replace(/\/\*[\s\S]*?\*\//g, "");
		const selectors = css
			.split("}")
			.map((rule) => rule.split("{")[0])
			.flatMap((list) => list.split(","))
			.map((s) => s.trim())
			.filter(Boolean);
		expect(selectors.length).toBeGreaterThan(10);
		const unscoped = selectors.filter((s) => !s.startsWith(".text-block pre "));
		expect(unscoped).toEqual([]);
	});
});
