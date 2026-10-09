import { describe, it, expect } from "vitest";
import { spliceAtCaret } from "./spliceAtCaret.js";

describe("spliceAtCaret", () => {
	it("inserts at the caret", () => {
		expect(spliceAtCaret("abcdef", "X", { selectionStart: 2, selectionEnd: 2 })).toBe("abXcdef");
	});

	it("replaces the selected range", () => {
		expect(spliceAtCaret("abcd", "X", { selectionStart: 1, selectionEnd: 3 })).toBe("aXd");
	});

	it("appends when there is no element", () => {
		expect(spliceAtCaret("abc", "X", null)).toBe("abcX");
	});
});
