import { describe, it, expect } from "vitest";
import { isReportable, buildReportPrefill } from "./reportableError";

describe("isReportable", () => {
	it("is true for a turn failure", () => expect(isReportable("MODEL_FAILED")).toBe(true));
	it("is true for an unknown failure", () => {
		expect(isReportable(null)).toBe(true);
		expect(isReportable("")).toBe(true);
	});
	it.each(["low_balance", "quota_exhausted", "user_limit_reached", "INTERRUPT_ALREADY_RESOLVED"])(
		"is false for %s",
		(code) => expect(isReportable(code)).toBe(false)
	);
});

describe("buildReportPrefill", () => {
	const at = "2026-11-17T10:00:00.000Z";
	it("carries message, code and time and leaves a blank line for the user", () => {
		const text = buildReportPrefill({ code: "MODEL_FAILED", message: "Model failed", at });
		expect(text).toBe(`Error: Model failed\nCode: MODEL_FAILED\nTime: ${at}\n\n`);
	});
	it("holds no session id", () => {
		expect(buildReportPrefill({ code: "X", message: "m", at })).not.toMatch(/sess|session/i);
	});
});
