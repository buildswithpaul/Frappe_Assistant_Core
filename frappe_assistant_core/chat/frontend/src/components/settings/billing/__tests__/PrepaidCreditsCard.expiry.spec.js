import { mount } from "@vue/test-utils";
import { describe, it, expect } from "vitest";

/**
 * The headline balance has a deadline, and used to admit it nowhere.
 *
 * Every ledger row below carries its own date, but nobody opens a ledger to
 * discover their balance expires — and the warning banner is silent until the
 * last 30 days. Between buying credits and the final month, the card showed a
 * number with no hint that part of it lapses.
 */

import PrepaidCreditsCard from "../PrepaidCreditsCard.vue";
// The note shows the amount the same way the balance above it does — "50K",
// not "50,000". Borrowing the helper keeps this test on "it names the amount"
// rather than pinning a formatting choice it does not own.
import { formatCredits } from "@/composables/useFormatters";

function inDays(days) {
	const d = new Date();
	d.setDate(d.getDate() + days);
	return d.toISOString();
}

function render(nextExpiry) {
	return mount(PrepaidCreditsCard, {
		props: { creditBalance: 50000, transactions: [], nextExpiry },
	});
}

function note(wrapper) {
	const el = wrapper.find(".credit-expiry-note");
	return el.exists() ? el.text().replace(/\s+/g, " ").trim() : null;
}

describe("PrepaidCreditsCard expiry note", () => {
	it("names the date when expiry is far off", () => {
		const text = note(render({ expires_at: inDays(300), credits: 50000 }));
		expect(text).toContain(`${formatCredits(50000)} credits expire on`);
		// A year out, "in 300 days" is noise — the date is the useful fact.
		expect(text).not.toMatch(/\bin \d+ days\b/);
	});

	it("counts down once it is close, and says so loudly", () => {
		const wrapper = render({ expires_at: inDays(9), credits: 4200 });
		expect(note(wrapper)).toContain(`${formatCredits(4200)} credits expire in 9 days`);
		expect(wrapper.find(".credit-expiry-note").classes()).toContain("soon");
	});

	it("is not shouting a year ahead of time", () => {
		const wrapper = render({ expires_at: inDays(300), credits: 50000 });
		expect(wrapper.find(".credit-expiry-note").classes()).not.toContain("soon");
	});

	it("says nothing when no batch is on a clock", () => {
		// Still true of credits bought before purchases had a validity window.
		expect(note(render(null))).toBeNull();
	});

	it("says nothing about a date already past", () => {
		expect(note(render({ expires_at: inDays(-3), credits: 100 }))).toBeNull();
	});

	it("leaves the per-batch ledger alone", () => {
		const wrapper = mount(PrepaidCreditsCard, {
			props: {
				creditBalance: 50000,
				nextExpiry: { expires_at: inDays(300), credits: 50000 },
				transactions: [
					{
						name: "AR-CRT-1",
						type: "Purchase",
						credits: 50000,
						source: "Prepaid Purchase",
						creation: new Date().toISOString(),
						expires_at: inDays(300),
					},
					{
						name: "AR-CRT-0",
						type: "Purchase",
						credits: 10000,
						source: "Prepaid Purchase",
						creation: new Date().toISOString(),
						expires_at: null,
					},
				],
			},
		});
		const rows = wrapper.findAll(".txn-expiry").map((e) => e.text());
		expect(rows[0]).toMatch(/^Expires /);
		// Sold before the window existed; perpetual remains the truth for it.
		expect(rows[1]).toBe("Never expires");
	});
});
