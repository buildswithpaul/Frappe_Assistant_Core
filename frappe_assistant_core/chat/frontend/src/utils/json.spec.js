import { describe, it, expect } from "vitest";
import { parseJsonMaybe } from "./json";

describe("parseJsonMaybe", () => {
	it("parses a JSON string and passes parsed values through", () => {
		expect(parseJsonMaybe('{"a":1}', null)).toEqual({ a: 1 });
		expect(parseJsonMaybe([1], null)).toEqual([1]);
	});

	it("returns the fallback for blank, null or malformed input", () => {
		expect(parseJsonMaybe("", [])).toEqual([]);
		expect(parseJsonMaybe(null, "x")).toBe("x");
		expect(parseJsonMaybe(undefined, 7)).toBe(7);
		expect(parseJsonMaybe("{oops", {})).toEqual({});
	});
});
