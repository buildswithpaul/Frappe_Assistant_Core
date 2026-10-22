import { describe, it, expect } from "vitest";
import { shortModelName } from "./modelName";

describe("shortModelName", () => {
	it("drops a leading vendor word", () => {
		expect(shortModelName("Claude Sonnet 4.6")).toBe("Sonnet 4.6");
		expect(shortModelName("Google Gemini 2.5 Flash")).toBe("Gemini 2.5 Flash");
	});

	it("keeps names that do not start with a vendor word", () => {
		expect(shortModelName("GPT-5.6 Terra")).toBe("GPT-5.6 Terra");
		expect(shortModelName("Auto")).toBe("Auto");
	});

	it("keeps a name that is only the vendor word", () => {
		expect(shortModelName("Claude")).toBe("Claude");
	});

	it("tolerates a missing name", () => {
		expect(shortModelName(undefined)).toBe("");
	});
});
