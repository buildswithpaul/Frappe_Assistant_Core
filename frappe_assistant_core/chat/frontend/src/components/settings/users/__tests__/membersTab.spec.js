import { describe, it, expect } from "vitest";
import {
	isIdle,
	inviteExpiry,
	seatChargeRequired,
	parseAuditDetails,
	describeAuditEntry,
} from "../memberHelpers";

// Note: relative-time display now uses the shared formatRelativeTime from
// @/composables/useFormatters (covered by its own tests). memberHelpers only
// owns isIdle, whose 30-day threshold the shared util doesn't replicate.

describe("isIdle", () => {
	it("flags users inactive for 30+ days", () => {
		const old = new Date(Date.now() - 31 * 86400 * 1000).toISOString();
		expect(isIdle(old)).toBe(true);
	});
	it("does not flag recently active users", () => {
		const recent = new Date(Date.now() - 2 * 86400 * 1000).toISOString();
		expect(isIdle(recent)).toBe(false);
	});
	it("treats never-active (null) as idle", () => {
		expect(isIdle(null)).toBe(true);
	});
});

describe("inviteExpiry", () => {
	it("reports days remaining for a fresh invite", () => {
		const now = new Date().toISOString();
		expect(inviteExpiry(now)).toMatch(/expires/i);
	});
	it("reports expired for an old invite", () => {
		const old = new Date(Date.now() - 8 * 86400 * 1000).toISOString();
		expect(inviteExpiry(old).toLowerCase()).toContain("expired");
	});
	it("handles null", () => {
		expect(typeof inviteExpiry(null)).toBe("string");
	});
	it("pins the day-count copy for a mid-window invite", () => {
		// ~3 days into a 7-day window → ~4 days left. Math.ceil on the
		// (just-under-4-day) remainder is deterministic at "expires in 4 days".
		const fourishDaysLeft = new Date(Date.now() - 3 * 86400 * 1000).toISOString();
		expect(inviteExpiry(fourishDaysLeft)).toBe("expires in 4 days");
	});
});

describe("seatChargeRequired", () => {
	const perUser = { is_per_user: true, price_per_user: 5999, min_users: 3 };

	it("false when no limit", () => {
		expect(seatChargeRequired(null)).toBe(false);
	});
	it("false within included seats", () => {
		expect(
			seatChargeRequired({ active_users: 2, min_users: 5, is_per_user: true, price_per_user: 10 })
		).toBe(false);
	});
	it("true at/over included seats with per-user pricing", () => {
		expect(
			seatChargeRequired({ active_users: 5, min_users: 5, is_per_user: true, price_per_user: 10 })
		).toBe(true);
	});
	it("false at limit when not per-user and no price", () => {
		expect(
			seatChargeRequired({ active_users: 5, min_users: 5, is_per_user: false, price_per_user: 0 })
		).toBe(false);
	});

	it("charges when every paid seat is taken", () => {
		expect(
			seatChargeRequired({ ...perUser, active_users: 3, paid_seats: 3, vacant_seats: 0 }),
		).toBe(true);
	});

	it("does not charge while a paid seat stands empty", () => {
		// The production case: 9 paid, 5 assigned. Adding the 6th costs nothing.
		expect(
			seatChargeRequired({ ...perUser, active_users: 5, paid_seats: 9, vacant_seats: 4 }),
		).toBe(false);
	});

	it("does not charge below the plan minimum", () => {
		expect(
			seatChargeRequired({ ...perUser, active_users: 1, paid_seats: 3, vacant_seats: 2 }),
		).toBe(false);
	});

	it("never charges on a flat plan", () => {
		// min_users is deliberately non-default (5, not the 999 fallback) so
		// this only stays green if the is_per_user guard is what's stopping
		// the charge -- not because active_users(9) happens to fall under an
		// unset minimum.
		expect(
			seatChargeRequired({
				is_per_user: false, active_users: 9, min_users: 5,
				paid_seats: null, vacant_seats: null,
			}),
		).toBe(false);
	});

	it("falls back to the seat minimum when vacancy data is missing", () => {
		// Older AR builds ship no vacant_seats; keep the previous behaviour.
		expect(
			seatChargeRequired({ ...perUser, active_users: 3, vacant_seats: undefined }),
		).toBe(true);
	});
});

describe("parseAuditDetails", () => {
	it("parses a JSON string", () => {
		expect(parseAuditDetails('{"new_role":"Admin"}')).toEqual({ new_role: "Admin" });
	});
	it("returns {} for null / bad JSON / already-object", () => {
		expect(parseAuditDetails(null)).toEqual({});
		expect(parseAuditDetails("not json")).toEqual({});
		expect(parseAuditDetails({ a: 1 })).toEqual({ a: 1 }); // tolerate already-parsed
	});
});

describe("describeAuditEntry", () => {
	it("phrases a role change with the new role", () => {
		const e = { action: "User Role Changed", actor: "a@e.com", target_user_id: "b@e.com", details: '{"new_role":"Admin"}' };
		const s = describeAuditEntry(e);
		expect(s).toContain("Admin");
		expect(s).toContain("b@e.com");
	});
	it("phrases an invite", () => {
		const e = { action: "User Invited", actor: "a@e.com", target_user_id: "b@e.com", details: "{}" };
		expect(describeAuditEntry(e).toLowerCase()).toContain("invited");
	});
	it("falls back gracefully for an unknown action", () => {
		const e = { action: "Something Else", actor: "a@e.com", target_user_id: "b@e.com", details: "{}" };
		expect(typeof describeAuditEntry(e)).toBe("string");
		expect(describeAuditEntry(e).length).toBeGreaterThan(0);
	});
	it("phrases user activated verb-first (composes with prepended actor)", () => {
		const e = { action: "User Activated", actor: "b@e.com", target_user_id: "b@e.com", details: "{}" };
		const s = describeAuditEntry(e);
		expect(s.toLowerCase()).toContain("joined");
		expect(s).not.toContain("b@e.com");  // verb-first: no target/actor echoed in the clause
	});
	it("handles a missing credit limit detail", () => {
		const e = { action: "User Credit Limit Changed", actor: "a@e.com", target_user_id: "b@e.com", details: "{}" };
		expect(describeAuditEntry(e)).toContain("—");
	});
	it("ignores array details", () => {
		expect(parseAuditDetails("[1,2,3]")).toEqual({});
		expect(parseAuditDetails([1, 2, 3])).toEqual({});
	});
});
