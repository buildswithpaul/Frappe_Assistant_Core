import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Redmine #34377: wide answer tables on a phone. jsdom injects no scoped CSS and has no layout,
// so the guard reads the component styles, as layout/sidebar-height.spec.js does.
const __dirname = dirname(fileURLToPath(import.meta.url));
const read = (p) => readFileSync(join(__dirname, p), "utf8");
const styleOf = (sfc) => sfc.slice(sfc.indexOf("<style"));

function rulesFor(css, selectorPattern) {
	const rx = new RegExp(`([^{}]*${selectorPattern}[^{}]*)\\{([^}]*)\\}`, "g");
	return [...css.matchAll(rx)].map((m) => ({ selector: m[1].trim(), body: m[2] }));
}

describe("answer tables on a phone", () => {
	const renderer = styleOf(read("../MessageBlockRenderer.vue"));
	const bubble = styleOf(read("../MessageBubble.vue"));

	it("sets monospace on figure cells only, never on every cell", () => {
		for (const css of [renderer, bubble]) {
			const mono = rulesFor(css, ":deep\\(td").filter((r) => /--ql-font-mono/.test(r.body));
			expect(mono.length).toBeGreaterThan(0);
			for (const rule of mono) expect(rule.selector).toMatch(/td\.md-num/);
		}
	});

	it("scrolls a wide table inside its own box", () => {
		const box = rulesFor(renderer, "\\.md-table-scroll\\)\\s*");
		const body = box.map((r) => r.body).join(";");
		expect(body).toMatch(/overflow-x:\s*auto/);
		expect(body).toMatch(/max-width:\s*100%/);
	});

	it("tightens table cells on small screens", () => {
		const media = renderer.match(/@media \(max-width: 640px\)\s*\{([\s\S]*?)\n\}/);
		expect(media).not.toBeNull();
		expect(media[1]).toMatch(/:deep\(td\)/);
		expect(media[1]).toMatch(/font-size/);
	});
});
