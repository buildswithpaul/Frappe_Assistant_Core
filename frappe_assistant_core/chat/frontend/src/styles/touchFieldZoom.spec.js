import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// iOS zooms the page into a focused field whose font is under 16px, and a home-screen app
// never zooms back out (Redmine #34376). jsdom has no layout or media queries, so the guard
// reads the stylesheet source, as quiet-ledger.spec.js does.
const __dirname = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(__dirname, "./quiet-ledger.css"), "utf8");
const indexHtml = readFileSync(join(__dirname, "../../index.html"), "utf8");

function coarsePointerBlock() {
	const start = css.search(/@media\s*\(pointer:\s*coarse\)\s*\{/);
	if (start === -1) return null;
	let depth = 0;
	for (let i = css.indexOf("{", start); i < css.length; i++) {
		if (css[i] === "{") depth++;
		if (css[i] === "}" && --depth === 0) return css.slice(start, i + 1);
	}
	return null;
}

describe("touch screens never zoom into a focused field", () => {
	it("gives text fields at least 16px on a coarse pointer", () => {
		const block = coarsePointerBlock();
		expect(block).not.toBeNull();
		for (const selector of [/\binput\b/, /\btextarea\b/, /\bselect\b/]) {
			expect(block).toMatch(selector);
		}
		const size = block.match(/font-size:\s*(\d+)px\s*!important/);
		expect(size).not.toBeNull();
		expect(Number(size[1])).toBeGreaterThanOrEqual(16);
	});

	it("keeps pinch-zoom: the viewport does not cap or disable scaling", () => {
		const viewport = indexHtml.match(/<meta name="viewport" content="([^"]+)"/);
		expect(viewport).not.toBeNull();
		expect(viewport[1]).not.toMatch(/maximum-scale/);
		expect(viewport[1]).not.toMatch(/user-scalable\s*=\s*no/);
	});
});
