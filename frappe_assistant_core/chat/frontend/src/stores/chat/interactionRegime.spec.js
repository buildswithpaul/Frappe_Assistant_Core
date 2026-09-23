import { describe, it, expect } from "vitest";
import { isApprovalInteraction } from "./interactionRegime";

describe("isApprovalInteraction", () => {
	it("is true for the literal 'approval' value", () => {
		expect(isApprovalInteraction("approval")).toBe(true);
	});

	it("defaults a missing value to approval", () => {
		expect(isApprovalInteraction(undefined)).toBe(true);
	});

	it("is false for the real ask_user value 'text_input'", () => {
		expect(isApprovalInteraction("text_input")).toBe(false);
	});

	it("is false for any other known question subtype", () => {
		expect(isApprovalInteraction("single_select")).toBe(false);
		expect(isApprovalInteraction("multi_select")).toBe(false);
		expect(isApprovalInteraction("confirm")).toBe(false);
	});

	it("is false for an unknown/future value", () => {
		expect(isApprovalInteraction("some_future_type")).toBe(false);
	});
});
