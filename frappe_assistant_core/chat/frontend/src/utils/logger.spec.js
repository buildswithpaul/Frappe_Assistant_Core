import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { resolve, join, relative, basename } from "node:path";

/**
 * Every log in the app has to flow through one of the two loggers — `logger`
 * in the SPA, `FACOLogger` in the widget — because only they know to stay
 * quiet outside developer mode. A raw `console.log` bypasses that gate and
 * ships debug noise into a customer's browser console.
 *
 * ESLint's `no-console` would catch this, but the JS hooks are disabled in
 * `.pre-commit-config.yaml`, so nothing enforced it and the calls crept back.
 * This scan is the enforcement.
 */

const APP_ROOT = resolve(process.cwd(), "../..");

const SKIP_DIRS = new Set([
	"node_modules",
	"libs", // vendored html2canvas-pro / DOMPurify
	"spa", // public/chat/spa — Vite build output, gitignored
	"__pycache__",
]);

// The loggers themselves are the one place console.* belongs.
const ALLOWED_FILES = new Set(["logger.js", "faco_logger.js"]);

const CONSOLE_CALL = /\bconsole\.\w+\s*\(/;

function collect(dir, found = []) {
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) {
			if (!SKIP_DIRS.has(entry)) collect(full, found);
			continue;
		}
		if (!/\.(js|vue)$/.test(entry)) continue;
		if (entry.endsWith(".spec.js") || entry.endsWith(".min.js")) continue;
		if (ALLOWED_FILES.has(basename(entry))) continue;
		found.push(full);
	}
	return found;
}

describe("no raw console calls outside the loggers", () => {
	it("scans a non-trivial number of files", () => {
		// Guards the guard: a broken path would make the assertion below vacuous.
		expect(collect(APP_ROOT).length).toBeGreaterThan(100);
	});

	it("finds none", () => {
		const offenders = collect(APP_ROOT)
			.filter((file) => CONSOLE_CALL.test(readFileSync(file, "utf8")))
			.map((file) => relative(APP_ROOT, file));

		expect(offenders).toEqual([]);
	});
});
