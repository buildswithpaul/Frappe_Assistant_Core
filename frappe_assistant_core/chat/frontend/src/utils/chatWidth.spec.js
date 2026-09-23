import { describe, it, expect } from "vitest";
import { CHAT_WIDTHS, resolveReadWidth } from "./chatWidth.js";

describe("resolveReadWidth", () => {
	it("maps cozy to 720px", () => {
		expect(resolveReadWidth("cozy")).toBe("720px");
	});
	it("maps wide to 960px", () => {
		expect(resolveReadWidth("wide")).toBe("960px");
	});
	it("falls back to wide for unknown values", () => {
		expect(resolveReadWidth(undefined)).toBe(CHAT_WIDTHS.wide);
		expect(resolveReadWidth("banana")).toBe("960px");
	});
});
