import { describe, it, expect } from "vitest";
import { lineDiff } from "./lineDiff";

const flat = (rows) => rows.map((r) => `${r.type}:${r.text}`);

describe("lineDiff", () => {
	it("marks removed and added lines and keeps unchanged ones as context", () => {
		expect(flat(lineDiff("a\nb\nc", "a\nx\nc"))).toEqual(["same:a", "del:b", "add:x", "same:c"]);
	});

	it("returns only context for identical text", () => {
		expect(flat(lineDiff("a\nb", "a\nb"))).toEqual(["same:a", "same:b"]);
	});

	it("handles pure insertions and deletions", () => {
		expect(flat(lineDiff("a", "a\nb"))).toEqual(["same:a", "add:b"]);
		expect(flat(lineDiff("a\nb", "b"))).toEqual(["del:a", "same:b"]);
	});

	it("treats empty old text as all added", () => {
		expect(flat(lineDiff("", "a\nb"))).toEqual(["add:a", "add:b"]);
	});

	it("copes with a 400-line script", () => {
		const old = Array.from({ length: 400 }, (_, i) => `line ${i}`).join("\n");
		const next = old.replace("line 200", "changed");
		const rows = lineDiff(old, next);
		expect(rows.filter((r) => r.type !== "same")).toHaveLength(2);
		expect(rows).toHaveLength(401);
	});
});
