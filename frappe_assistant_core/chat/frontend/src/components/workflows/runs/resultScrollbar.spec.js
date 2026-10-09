import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

const dir = path.dirname(new URL(import.meta.url).pathname);

// A real scrollbar does not exist in jsdom, so this pins the rule that themes it:
// without scrollbar-color the track renders as a bright rail in dark mode.
function rule(file, selector) {
	const css = fs.readFileSync(path.join(dir, file), "utf8");
	const start = css.indexOf(`\n${selector} {`);
	expect(start, `${selector} rule in ${file}`).toBeGreaterThan(-1);
	return css.slice(start, css.indexOf("}", start));
}

describe("result box scrollbars use theme tokens", () => {
	it.each([
		["RunCardDetails.vue", ".result-body"],
		["OutputFullscreen.vue", ".fs-body"],
	])("%s %s", (file, selector) => {
		expect(rule(file, selector)).toContain("scrollbar-color: var(--ql-border) transparent");
	});
});
