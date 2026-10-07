import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Vitest turns imported CSS into an empty string, so read the source file.
const preflight = readFileSync(resolve(__dirname, "preflight.css"), "utf8");

describe("widget preflight", () => {
	it("gives every element border-box sizing, as Tailwind does in the SPA", () => {
		expect(preflight).toMatch(/\*,\s*::before,\s*::after\s*\{[^}]*box-sizing:\s*border-box/);
	});

	it("keeps no unresolved theme() call", () => {
		expect(preflight).not.toMatch(/theme\(/);
	});

	it("keeps the :host form so the shadow-host plugin can retarget it", () => {
		expect(preflight).toMatch(/html,\s*:host\s*\{/);
	});
});
