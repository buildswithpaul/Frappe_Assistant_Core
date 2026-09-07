import { describe, expect, it } from "vitest";
import { INDIAN_STATES, validateBillingForm } from "./billingValidation";

// Mirrors what the server enforces (assistant_runtime_payments
// api/billing_details._validate_billing_input). This runs first only so the
// customer sees the problem without a round trip — the server stays
// authoritative, and it is the one holding India Compliance's tables.
const valid = (over = {}) => ({
	billing_legal_name: "Northwind Trading Pvt Ltd",
	billing_email: "accounts@northwind.example",
	billing_phone: "+919900000000",
	billing_country: "IN",
	billing_state: "Karnataka",
	billing_city: "Bengaluru",
	billing_address_line1: "Tower C",
	billing_pincode: "560017",
	gstin: "",
	...over,
});

describe("validateBillingForm", () => {
	it("accepts a complete Indian address", () => {
		expect(validateBillingForm(valid())).toEqual({});
	});

	it.each([
		["billing_legal_name", { billing_legal_name: "  " }],
		["billing_email", { billing_email: "not-an-email" }],
		["billing_phone", { billing_phone: "" }],
		["billing_address_line1", { billing_address_line1: "" }],
		["billing_city", { billing_city: "" }],
		["billing_state", { billing_state: "" }],
	])("names %s when it is missing or malformed", (field, over) => {
		const errors = validateBillingForm(valid(over));
		expect(Object.keys(errors)).toContain(field);
		expect(errors[field]).toBeTruthy();
	});

	it("does not demand a state outside India", () => {
		const errors = validateBillingForm(
			valid({ billing_country: "US", billing_state: "", billing_pincode: "10001" })
		);
		expect(errors).toEqual({});
	});

	it("rejects a postal code that is not six digits, in India only", () => {
		expect(validateBillingForm(valid({ billing_pincode: "56001" })))
			.toHaveProperty("billing_pincode");
		expect(validateBillingForm(valid({ billing_pincode: "056001" })))
			.toHaveProperty("billing_pincode");
	});

	it("rejects a GSTIN of the wrong shape", () => {
		expect(validateBillingForm(valid({ gstin: "29AAHCM7727Q1Z" })))
			.toHaveProperty("gstin");
	});

	it("accepts a well-formed GSTIN", () => {
		expect(validateBillingForm(valid({ gstin: "29AAHCM7727Q1ZI" }))).toEqual({});
	});

	it("catches a GSTIN whose state code contradicts the selected state", () => {
		// 29 is Karnataka. The server enforces this too; catching it here saves
		// a round trip on a mistake that would otherwise reach a tax invoice as
		// the wrong place of supply.
		const errors = validateBillingForm(
			valid({ gstin: "29AAHCM7727Q1ZI", billing_state: "Maharashtra" })
		);
		expect(errors).toHaveProperty("gstin");
	});

	it("ships every state India Compliance knows, and no others", () => {
		// IC's STATE_NUMBERS minus "Other Countries" (96), which is not an
		// Indian state — a foreign party is modelled here as a non-India
		// country instead.
		expect(INDIAN_STATES).toHaveLength(37);
		expect(INDIAN_STATES).toContain("Karnataka");
		expect(INDIAN_STATES).toContain("Ladakh");
		expect(INDIAN_STATES).not.toContain("Other Countries");
	});

	it("names Lakshadweep the way the server does", () => {
		// The old hand-maintained list said "Lakshadweep"; India Compliance
		// calls it "Lakshadweep Islands", so the server rejected the only
		// value the dropdown could produce and that territory could never
		// save its billing details.
		expect(INDIAN_STATES).toContain("Lakshadweep Islands");
		expect(INDIAN_STATES).not.toContain("Lakshadweep");
		expect(
			validateBillingForm(valid({ billing_state: "Lakshadweep" }))
		).toHaveProperty("billing_state");
	});
});
