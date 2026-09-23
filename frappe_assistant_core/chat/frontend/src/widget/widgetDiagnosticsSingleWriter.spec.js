import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const WIDGET_JS = resolve(process.cwd(), "../../public/chat/widget/widget.js");

/**
 * Regression guard for a bug that actually shipped: FACODiagnostics.setEnabled
 * once had two writers — one in init() reading check_access()'s response, one
 * in load_widget_settings() reading get_widget_settings()'s response. Both
 * endpoints' documented exception-fallback shapes omit the field they'd need
 * to agree, so whichever call happened to run second silently won — on the
 * exact scenario that matters (operator turns diagnostics off, then
 * get_widget_settings() hits its except-fallback), the second writer
 * re-enabled and re-persisted "on" over a correct "off".
 *
 * The fix is structural (delete the second writer), so the guard is
 * structural too: a source scan, not an execution test — mounting the whole
 * FACOWidget class to prove a deleted code path stays deleted is more
 * machinery than the invariant needs.
 */
describe("diagnostics kill switch has exactly one writer", () => {
	it("widget.js calls FACODiagnostics.setEnabled exactly once", () => {
		const source = readFileSync(WIDGET_JS, "utf8");
		const calls = source.match(/FACODiagnostics\.setEnabled\(/g) || [];
		expect(calls).toHaveLength(1);
	});

	it("load_widget_settings() does not touch FACODiagnostics", () => {
		const source = readFileSync(WIDGET_JS, "utf8");
		// Unique to the removed second writer: writer 1 (in init(), reading
		// check_access()) uses `access.enable_browser_diagnostics`, never this.
		expect(source).not.toContain("privacy.enable_browser_diagnostics");
	});
});
