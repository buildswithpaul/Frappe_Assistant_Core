import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

// The kit every FAC Page is drawn with; the page tools and FACO's skills rely on these classes.
const KIT = readFileSync(resolve(import.meta.dirname, "../../../../public/css/mockup_kit.css"), "utf-8");

describe("the mockup kit", () => {
	it.each([
		".mk-section",
		".mk-section-head",
		".mk-section-meta",
		".mk-list",
		".mk-text",
		".mk-edit-row",
		".mk-edit-error",
		".mk-sev-high",
		".mk-sev-med",
		".mk-sev-low",
		".mk-status-done",
		".mk-status-pending",
		".mk-period",
		".fac-presenting",
		".fac-present-off",
	])("styles %s", (selector) => {
		expect(KIT).toContain(selector);
	});
});

// A page follows Desk's theme: data-theme="dark" on the document (a frame) or on the shadow host.
describe("the mockup kit's themes", () => {
	const blocks = (css) => [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(([, selector, body]) => ({ selector: selector.trim(), body }));
	const tokens = (selector) => blocks(KIT).find((block) => block.selector.endsWith(selector))?.body || "";
	const literal = /#[0-9a-f]{3,8}\b|rgba?\(/i;

	it("keeps every colour in a theme token, so a dark page has no light patches", () => {
		const outside = blocks(KIT).filter((block) => !block.selector.includes(":root") && literal.test(block.body));
		expect(outside.map((block) => block.selector)).toEqual([]);
	});

	it("gives every light token a dark value", () => {
		const names = (body) => [...body.matchAll(/(--mk-[\w-]+):\s*[^;]*(#|rgb)/g)].map(([, name]) => name).sort();
		const light = names(tokens(":root,\n:host"));
		expect(light.length).toBeGreaterThan(10);
		expect(names(tokens(':root[data-theme="dark"],\n\t:host([data-theme="dark"])'))).toEqual(light);
	});

	it("is dark on screen only, so a page still prints light", () => {
		expect(KIT).toMatch(/@media screen\s*\{\s*:root\[data-theme="dark"\],\s*:host\(\[data-theme="dark"\]\)\s*\{/);
	});
});
