import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
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

let Quota;

beforeAll(() => {
	globalThis.__ = (s, args) =>
		args ? s.replace(/\{(\d+)\}/g, (_m, i) => args[i]) : s;
	// eslint-disable-next-line no-new-func
	new Function(readFileSync(quotaJs, "utf8"))();
	Quota = window.FACOWidgetQuota;
});

beforeEach(() => {
	sessionStorage.clear();
});

function fired(status) {
	const calls = { blocked: 0, overage: 0, warning: [] };
	const stub = {
		...Quota,
		show_quota_blocked_modal: () => calls.blocked++,
		show_quota_overage_notice: () => calls.overage++,
		show_quota_warning_modal: (_w, t) => calls.warning.push(t),
	};
	stub.check_quota_warnings({}, status);
	return calls;
}

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

describe("widget quota modals", () => {
	const admin = { is_admin: true };

	it("shows the overage notice, not the block, while prepaid credits remain", () => {
		const calls = fired({
			...admin,
			percentage_used: 100,
			in_overage: true,
			credits_exhausted: false,
			credit_balance: 25000,
		});
		expect(calls.overage).toBe(1);
		expect(calls.blocked).toBe(0);
	});

	it("shows the overage notice only once per session", () => {
		const status = { ...admin, percentage_used: 100, in_overage: true, credit_balance: 500 };
		expect(fired(status).overage).toBe(1);
		expect(fired(status).overage).toBe(0);
	});

	it("blocks once every credit is gone", () => {
		const calls = fired({
			...admin,
			percentage_used: 100,
			in_overage: false,
			credits_exhausted: true,
			credit_balance: 0,
		});
		expect(calls.blocked).toBe(1);
		expect(calls.overage).toBe(0);
	});

	it("keeps the 80 and 90 percent warnings — they are the nudge to buy", () => {
		expect(fired({ ...admin, percentage_used: 85 }).warning).toEqual([80]);
		expect(fired({ ...admin, percentage_used: 95 }).warning).toEqual([90]);
	});

	it("tells a non-admin nothing at all", () => {
		const calls = fired({
			is_admin: false,
			percentage_used: 100,
			in_overage: true,
			credit_balance: 25000,
		});
		expect(calls.overage).toBe(0);
		expect(calls.blocked).toBe(0);
	});
});

describe("overage notice content", () => {
	it("names the remaining balance so the admin knows the runway", () => {
		let opts;
		globalThis.frappe = { ui: { Dialog: class { constructor(o) { opts = o; } show() {} } } };

		Quota.show_quota_overage_notice({ quota_status: { credit_balance: 25000 } }, true);

		const html = opts.fields[0].options;
		expect(html).toContain("25.0K");
		expect(opts.primary_action_label).toBeTruthy();
	});
});
