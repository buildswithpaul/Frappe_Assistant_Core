import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect, vi, afterEach } from "vitest";
import { randomUUID } from "./uuid";

const SRC = join(import.meta.dirname, "..");

function sourceFiles(dir) {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		if (statSync(path).isDirectory()) return sourceFiles(path);
		return /\.(js|vue)$/.test(name) && !/\.spec\.js$/.test(name) ? [path] : [];
	});
}

describe("randomUUID", () => {
	afterEach(() => vi.restoreAllMocks());

	it("makes version 4 UUIDs, a new one each time", () => {
		const ids = new Set(Array.from({ length: 50 }, randomUUID));

		expect(ids.size).toBe(50);
		for (const id of ids) {
			expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
		}
	});

	it("works where crypto.randomUUID doesn't exist (a site on plain http)", () => {
		vi.spyOn(crypto, "randomUUID").mockImplementation(() => {
			throw new TypeError("crypto.randomUUID is not a function");
		});

		expect(randomUUID()).toHaveLength(36);
	});

	it("is what the app uses: no crypto.randomUUID call is left in src", () => {
		const callers = sourceFiles(SRC).filter((path) => /crypto\.randomUUID\(/.test(readFileSync(path, "utf8")));

		expect(callers).toEqual([]);
	}, 20000); // reads every source file: slow when the whole suite runs at once
});
