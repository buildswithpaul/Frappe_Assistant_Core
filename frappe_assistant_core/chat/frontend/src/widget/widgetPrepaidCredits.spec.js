import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

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

const quotaJs = resolve(process.cwd(), "../../public/chat/widget/widget_quota.js");

const spotlightJs = resolve(process.cwd(), "../../public/chat/widget/widget_spotlight.js");

let Quota;
let Spotlight;

beforeAll(() => {
	globalThis.__ = (s, args) =>
		args ? s.replace(/\{(\d+)\}/g, (_m, i) => args[i]) : s;
	// eslint-disable-next-line no-new-func
	new Function(readFileSync(spotlightJs, "utf8"))();
	new Function(readFileSync(quotaJs, "utf8"))();
	Quota = window.FACOWidgetQuota;
	Spotlight = window.FACOWidgetSpotlight;
});

beforeEach(() => {
	localStorage.clear();
});

const USER = "owner@acme.com";
const check = (status) => Quota.check_quota_warnings({ user: USER }, status);

describe("widget send gate", () => {
	it("allows the turn when prepaid credits are covering the overage", () => {
		expect(
			Quota.is_blocked({
				percentage_used: 100,
				credit_balance: 25000,
				in_overage: true,
				credits_exhausted: false,
			}),
		).toBe(false);
	});

	it("still blocks when the quota AND the prepaid balance are both gone", () => {
		expect(
			Quota.is_blocked({
				percentage_used: 100,
				credit_balance: 0,
				in_overage: false,
				credits_exhausted: true,
			}),
		).toBe(true);
	});

	it("never blocks an unlimited tenant", () => {
		expect(Quota.is_blocked({ is_unlimited: true, credits_exhausted: true })).toBe(false);
	});

	it("does not block when the quota status is missing", () => {
		expect(Quota.is_blocked(null)).toBe(false);
		expect(Quota.is_blocked(undefined)).toBe(false);
	});

	it("does not block on a server too old to answer", () => {
		// Widget assets are cached for 12h, so a stale bundle meeting a new
		// server — or the reverse — is routine. An absent answer is not a "no".
		expect(Quota.is_blocked({ percentage_used: 140 })).toBe(false);
	});
});

describe("widget quota moments", () => {
	const admin = { is_admin: true };

	it("announces the overage switchover, not a block, while prepaid credits remain", () => {
		const moment = check({
			...admin,
			percentage_used: 100,
			in_overage: true,
			credits_exhausted: false,
			credit_balance: 25000,
			billing_cycle_start: "2026-09-24",
		});
		expect(moment).toEqual({ kind: "overage" });
	});

	it("keeps announcing the overage until the notice actually renders", () => {
		const status = { ...admin, percentage_used: 100, in_overage: true, credit_balance: 500, billing_cycle_start: "2026-09-24" };
		expect(check(status)).toEqual({ kind: "overage" });
		expect(check(status)).toEqual({ kind: "overage" });
		expect(localStorage.getItem(`fac_quota_moment:${USER}:2026-09-24:overage`)).toBeNull();
	});

	it("returns the 100 moment once every credit is gone", () => {
		const moment = check({ ...admin, percentage_used: 100, credits_exhausted: true, credit_balance: 0 });
		expect(moment.kind).toBe("quota");
		expect(moment.threshold).toBe(100);
	});

	it("returns the 80 moment at 85 percent", () => {
		expect(check({ ...admin, percentage_used: 85 }).threshold).toBe(80);
	});

	it("has no 90 moment: 95 percent is still the 80 moment", () => {
		expect(check({ ...admin, percentage_used: 95 }).threshold).toBe(80);
	});

	it("stays quiet once the cycle key is set, and below 80", () => {
		const status = { ...admin, percentage_used: 85, billing_cycle_start: "2026-09-24" };
		expect(check(status)).not.toBeNull();
		Spotlight.storage_set(Spotlight.quota_key(USER, "2026-09-24", 80), "1");
		expect(check(status)).toBeNull();
		expect(check({ ...admin, percentage_used: 50 })).toBeNull();
	});

	it("tells a non-admin nothing at all", () => {
		expect(check({ is_admin: false, percentage_used: 100, in_overage: true, credit_balance: 25000 })).toBeNull();
		expect(check({ is_admin: false, credits_exhausted: true })).toBeNull();
	});
});

describe("overage notice", () => {
	const status = { success: true, is_admin: true, percentage_used: 100, in_overage: true, credit_balance: 25000, billing_cycle_start: "2026-09-24" };
	const key = `fac_quota_moment:${USER}:2026-09-24:overage`;
	let render_notice;

	beforeEach(() => {
		render_notice = vi.fn();
		window.FACOWidgetSpotlight = { ...Spotlight, render_notice, update_dot: vi.fn() };
		globalThis.frappe = { session: { user: USER }, call: vi.fn(async () => ({ message: status })) };
		globalThis.FACOLogger = { error: vi.fn() };
	});

	afterEach(() => {
		window.FACOWidgetSpotlight = Spotlight;
	});

	it("names the remaining balance and marks the cycle once it renders", async () => {
		await Quota.fetch_quota_status({ user: USER, is_open: true });

		expect(render_notice).toHaveBeenCalledTimes(1);
		expect(render_notice.mock.calls[0][1]).toContain("25.0K");
		expect(localStorage.getItem(key)).toBe("1");
	});

	it("holds the notice while the panel is closed and shows it on the next open", async () => {
		const widget = { user: USER, is_open: false };
		await Quota.fetch_quota_status(widget);

		expect(render_notice).not.toHaveBeenCalled();
		expect(localStorage.getItem(key)).toBeNull();

		widget.is_open = true;
		Quota.show_pending_overage_notice(widget);
		expect(render_notice).toHaveBeenCalledTimes(1);
		expect(localStorage.getItem(key)).toBe("1");

		Quota.show_pending_overage_notice(widget);
		expect(render_notice).toHaveBeenCalledTimes(1);
	});

	it("does not show it again in a cycle where it was already seen", async () => {
		localStorage.setItem(key, "1");
		await Quota.fetch_quota_status({ user: USER, is_open: true });
		expect(render_notice).not.toHaveBeenCalled();
	});
});
