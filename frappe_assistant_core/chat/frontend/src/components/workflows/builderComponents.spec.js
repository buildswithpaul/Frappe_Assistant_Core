import { describe, it, expect } from "vitest";

/**
 * Every builder component must actually compile.
 *
 * VariableInserter shipped for months with a template Vue could not parse
 * (`{{ '{{' + v + '}}' }}` — the interpolation ends at the first "}}"), and
 * nothing caught it because nothing imported the file. A component with no
 * `render` never reached a screen.
 */
const COMPONENTS = import.meta.glob(
	[
		"./*.vue",
		"./builder/*.vue",
		"./config/*.vue",
		"./toolbar/*.vue",
		"./nodes/*.vue",
		"./triggers/*.vue",
		"../../views/WorkflowBuilder.vue",
		"../../views/WorkflowList.vue",
	],
	{ eager: false }
);

describe("workflow builder components", () => {
	it("finds the builder component tree", () => {
		expect(Object.keys(COMPONENTS).length).toBeGreaterThan(20);
	});

	for (const [path, load] of Object.entries(COMPONENTS)) {
		it(`compiles ${path}`, async () => {
			const mod = await load();
			expect(typeof mod.default.render === "function" || !!mod.default.setup).toBe(true);
		});
	}
});
