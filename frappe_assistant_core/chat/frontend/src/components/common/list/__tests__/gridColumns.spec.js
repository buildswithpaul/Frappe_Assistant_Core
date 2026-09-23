import { describe, it, expect } from "vitest";
import { columnsForWidth } from "../gridColumns";

describe("columnsForWidth", () => {
	it("returns 4 columns at >= 1040px", () => {
		expect(columnsForWidth(1200)).toBe(4);
		expect(columnsForWidth(1040)).toBe(4);
	});
	it("returns 3 columns between 780 and 1039px", () => {
		expect(columnsForWidth(1039)).toBe(3);
		expect(columnsForWidth(780)).toBe(3);
	});
	it("returns 2 columns between 520 and 779px", () => {
		expect(columnsForWidth(779)).toBe(2);
		expect(columnsForWidth(520)).toBe(2);
	});
	it("returns 1 column below 520px", () => {
		expect(columnsForWidth(519)).toBe(1);
		expect(columnsForWidth(0)).toBe(1);
	});
	it("treats invalid input as 1 column", () => {
		expect(columnsForWidth(undefined)).toBe(1);
		expect(columnsForWidth(NaN)).toBe(1);
	});
});
