import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// jsdom does not apply scoped SFC styles, so a computed-style mount would prove nothing:
// these assert the declarations that undo preflight's resets are in the style source.
const style = (file) => {
	const source = readFileSync(resolve(__dirname, file), "utf8");
	return source.slice(source.indexOf("<style"));
};
const rule = (css, selector) => css.match(new RegExp(`(?:^|\\n)${selector}\\s*\\{([^}]*)\\}`))?.[1] || "";

describe("widget-only styles under preflight", () => {
	it("keeps the setup gate heading bold", () => {
		expect(rule(style("WidgetSetupGate.vue"), "h2")).toMatch(/font-weight:\s*600/);
	});

	it("keeps a hit target on the overage dismiss button", () => {
		expect(rule(style("OverageNotice.vue"), "\\.on-dismiss")).toMatch(/padding:\s*2px 4px/);
	});

	it("rests the header actions on the secondary text colour", () => {
		expect(rule(style("WidgetPanel.vue"), "\\.wp-actions button")).toMatch(/color:\s*var\(--ql-text-secondary\)/);
	});

	// FAC Chat loads robot.css from its own entry, so a shared FacoRobot in the panel draws nothing without it.
	it("loads the robot's stylesheet for the welcome masthead", () => {
		const entry = readFileSync(resolve(__dirname, "main.js"), "utf8");
		expect(entry).toMatch(/import\s+["']@\/styles\/robot\.css["']/);
	});
});
