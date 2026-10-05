import { describe, it, expect } from "vitest";
import { paymentFailureLines, shortDate } from "../paymentFailureCopy";

const RBI =
	"This saved card is no longer compliant with the RBI guidelines. Please use another card/payment method.";
const retrying = {
	reason: RBI,
	failed_at: "2026-10-05 00:02:47",
	invoice: "AR-INV-1",
	dunning_level: "Warning",
	attempt: 1,
	total_attempts: 4,
	next_retry_on: "2026-10-06",
	past_due: false,
};

describe("shortDate", () => {
	it("formats dates and datetimes without a timezone shift", () => {
		expect(shortDate("2026-10-06")).toBe("6 Oct");
		expect(shortDate("2026-10-05 00:02:47")).toBe("5 Oct");
		expect(shortDate("")).toBe("");
		expect(shortDate("not a date")).toBe("");
	});
});

describe("paymentFailureLines", () => {
	it("is null when nothing is failing", () => {
		expect(paymentFailureLines(null)).toBeNull();
		expect(paymentFailureLines(undefined)).toBeNull();
	});

	it("says what failed, why, and when we retry", () => {
		expect(paymentFailureLines(retrying)).toEqual({
			headline: "Your payment on 5 Oct didn't go through.",
			reason: RBI,
			retry: "We'll try again on 6 Oct (attempt 2 of 4).",
			pastDue: false,
		});
	});

	it("has no retry line once retries ran out", () => {
		const lines = paymentFailureLines({
			...retrying,
			past_due: true,
			attempt: 4,
			next_retry_on: null,
		});
		expect(lines.retry).toBe("");
		expect(lines.pastDue).toBe(true);
	});

	it("keeps an empty reason empty", () => {
		expect(paymentFailureLines({ ...retrying, reason: "" }).reason).toBe("");
	});
});
