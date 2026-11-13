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
	])("styles %s", (selector) => {
		expect(KIT).toContain(selector);
	});
});
