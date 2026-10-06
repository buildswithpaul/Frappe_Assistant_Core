import { describe, it, expect, beforeEach } from "vitest";
import { isBlocked, overageNoticeDue, markOverageNoticeShown } from "./quotaGate.js";

/**
 * A tenant who buys prepaid credits can keep working — AR admits the turn
 * whenever the balance is above zero. The widget did not: it refused to send
 * whenever `percentage_used >= 100`, a figure covering the monthly plan quota
 * alone. So the people who had just paid to stay unblocked were the only ones
 * the widget blocked, while the SPA (which has no client-side gate) served
 * them fine.
 *
 * The gate now asks the server's `credits_exhausted`, which is AR's own rule.
 */

beforeEach(() => {
	localStorage.clear();
});

const USER = "owner@acme.com";

describe("widget send gate", () => {
	it("allows the turn when prepaid credits are covering the overage", () => {
		expect(
			isBlocked({
				percentage_used: 100,
				credit_balance: 25000,
				in_overage: true,
				credits_exhausted: false,
			}),
		).toBe(false);
	});

	it("still blocks when the quota AND the prepaid balance are both gone", () => {
		expect(
			isBlocked({
				percentage_used: 100,
				credit_balance: 0,
				in_overage: false,
				credits_exhausted: true,
			}),
		).toBe(true);
	});

	it("never blocks an unlimited tenant", () => {
		expect(isBlocked({ is_unlimited: true, credits_exhausted: true })).toBe(false);
	});

	it("does not block when the quota status is missing", () => {
		expect(isBlocked(null)).toBe(false);
		expect(isBlocked(undefined)).toBe(false);
	});

	it("does not block on a server too old to answer", () => {
		// Widget assets are cached for 12h, so a stale bundle meeting a new
		// server — or the reverse — is routine. An absent answer is not a "no".
		expect(isBlocked({ percentage_used: 140 })).toBe(false);
	});
});

describe("overage notice", () => {
	const status = {
		success: true,
		is_admin: true,
		percentage_used: 100,
		in_overage: true,
		credit_balance: 25000,
		billing_cycle_start: "2026-09-24",
	};
	// The exact key the old widget wrote: users who dismissed this cycle's notice stay dismissed.
	const key = `fac_quota_moment:${USER}:2026-09-24:overage`;

	it("is due while prepaid credits cover the overage", () => {
		expect(overageNoticeDue({ ...status, credits_exhausted: false }, USER)).toBe(true);
	});

	it("stays due until the notice is marked shown, so one decided while closed is not spent unseen", () => {
		expect(overageNoticeDue(status, USER)).toBe(true);
		expect(overageNoticeDue(status, USER)).toBe(true);
		expect(localStorage.getItem(key)).toBeNull();
	});

	it("writes the legacy once-per-cycle key when marked shown, then is no longer due", () => {
		markOverageNoticeShown(status, USER);
		expect(localStorage.getItem(key)).toBe("1");
		expect(overageNoticeDue(status, USER)).toBe(false);
	});

	it("does not show it again in a cycle where it was already seen", () => {
		localStorage.setItem(key, "1");
		expect(overageNoticeDue(status, USER)).toBe(false);
	});

	it("is due again in the next billing cycle", () => {
		markOverageNoticeShown(status, USER);
		expect(overageNoticeDue({ ...status, billing_cycle_start: "2026-10-24" }, USER)).toBe(true);
	});

	it("is not due once every credit is gone (that is a block, not a switchover)", () => {
		expect(overageNoticeDue({ ...status, credits_exhausted: true }, USER)).toBe(false);
	});

	it("tells a non-admin nothing at all", () => {
		expect(overageNoticeDue({ ...status, is_admin: false }, USER)).toBe(false);
		expect(overageNoticeDue(null, USER)).toBe(false);
	});
});
