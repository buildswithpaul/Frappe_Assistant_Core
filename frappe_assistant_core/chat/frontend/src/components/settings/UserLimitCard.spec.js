import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import UserLimitCard from "./UserLimitCard.vue";

// The production case that started this task: the plan card said "5 seats"
// (assigned_seats/active_users) beside a hero computed from 9 paid seats.
const paidTeam = (over) => ({
	plan: "Team",
	is_per_user: true,
	paid_seats: 9,
	assigned_seats: 5,
	max_users: 20,
	remaining: 11,
	is_unlimited: false,
	...over,
});

function mountCard(props) {
	return mount(UserLimitCard, {
		props: { minUsers: 3, pricePerUser: 1999, ...props },
	});
}

describe("UserLimitCard", () => {
	it("names both the assigned and paid seat counts in the header", () => {
		const w = mountCard({ userLimit: paidTeam() });
		expect(w.text()).toContain("5");
		expect(w.text()).toContain("of");
		expect(w.text()).toContain("9");
		expect(w.text()).toMatch(/seats assigned/i);
	});

	it("occupancy reads assigned_seats, not active_users", () => {
		// A mutant that falls back to active_users only dies when the two
		// disagree -- so this fixture deliberately makes them disagree.
		const w = mountCard({
			userLimit: paidTeam({ assigned_seats: 5, active_users: 20 }),
		});
		const header = w.find(".limit-value").text();
		expect(header).toContain("5");
		expect(header).not.toContain("20");
	});

	it("falls back to active_users when assigned_seats is absent", () => {
		const w = mountCard({
			userLimit: paidTeam({ assigned_seats: undefined, active_users: 7 }),
		});
		expect(w.find(".limit-value").text()).toContain("7");
	});

	it("extra seats are paid minus the minimum, not assigned minus the minimum", () => {
		// Production case: 9 paid, 5 assigned, 3 minimum. Extra seats billed
		// are 6 (9-3); computing off assigned would say 2 (5-3).
		const w = mountCard({ userLimit: paidTeam() });
		expect(w.text()).toContain("3 included + 6 additional seat");
	});

	it("paid seats falls back to max(assigned, minimum) when the backend omits paid_seats", () => {
		// assigned=1, minimum=3: max(1,3)=3, distinct from assigned_seats(1)
		// itself. A mutant that reads `?? activeUsers.value` (dropping the
		// minimum floor) would say "of 1" instead of "of 3".
		const w = mountCard({
			userLimit: paidTeam({ paid_seats: undefined, assigned_seats: 1 }),
			minUsers: 3,
		});
		const header = w.find(".limit-value").text();
		expect(header).toContain("1");
		expect(header).toContain("of");
		expect(header).toContain("3");
	});

	it("shows the plain user count on a non-per-user plan, not an invented seat cap", () => {
		// Free plan: no seats are sold, so there is no paid_seats figure at
		// all. The header must fall back to active_users/max_users rather
		// than inventing a cap equal to headcount (which would read "2 of 2"
		// beside a progress bar and "slots remaining" line computed from a
		// real 3-seat max -- three numbers on one card again).
		const w = mountCard({
			userLimit: {
				plan: "Free",
				is_per_user: false,
				is_unlimited: false,
				paid_seats: null,
				active_users: 2,
				max_users: 3,
				remaining: 1,
			},
		});
		const header = w.find(".limit-value").text();
		expect(header).toContain("2");
		expect(header).toContain("3");
		expect(header).not.toMatch(/seats assigned/i);
	});

	it("shows the infinity symbol on an unlimited non-per-user plan", () => {
		const w = mountCard({
			userLimit: {
				plan: "Enterprise",
				is_per_user: false,
				is_unlimited: true,
				paid_seats: null,
				active_users: 5,
				max_users: -1,
			},
		});
		const header = w.find(".limit-value").text();
		expect(header).toContain("∞");
		expect(header).not.toMatch(/seats assigned/i);
	});

	it("hides the additional-seat breakdown on a non-per-user plan, not just the header", () => {
		// Realistic Free-plan shape: min_users defaults to 1 for any plan
		// lacking real subscription data (chat/api/users.py's subscription
		// enrichment), so the old extraSeats fallback -- Math.max(active_users,
		// minUsers) minus minUsers -- was almost always positive. Gating just
		// the header left this block still reading it, eight lines down: the
		// same three-numbers-on-one-card defect Finding 1 targeted.
		//
		// pricePerUser is pinned to 0 here (a genuine Free plan's) so this
		// test isolates the extraSeats/paidSeats-driven block under test --
		// the separate seat-pricing-notice/upgrade-hint blocks are driven by
		// pricePerUser alone and are a different, out-of-scope mechanism.
		const w = mountCard({
			userLimit: {
				plan: "Free",
				is_per_user: false,
				is_unlimited: false,
				paid_seats: null,
				active_users: 2,
				max_users: 3,
				remaining: 1,
			},
			minUsers: 1,
			pricePerUser: 0,
		});
		// Assert on the whole card, not just .limit-value -- this block sits
		// eight lines below the header and would survive a header-only check.
		expect(w.text()).not.toContain("additional seat");
	});

	it("renders the backend's credit pool, not a client recomputation", () => {
		// credits_per_user (100) x assigned (5) = 500, and x paid (9) = 900.
		// Neither is right: a mid-cycle seat's credits are prorated, so the
		// pool must come straight from the subscription's credit_quota.
		const w = mountCard({
			userLimit: paidTeam(),
			creditsPerUser: 100,
			creditQuota: 12345,
		});
		expect(w.find(".pool-value").text()).toContain("12,345");
		expect(w.find(".pool-value").text()).not.toContain("500");
		expect(w.find(".pool-value").text()).not.toContain("900");
	});

	it("renders a zero credit pool on a payments-less install rather than hiding it as unknown", () => {
		const w = mountCard({
			userLimit: paidTeam(),
			creditsPerUser: 100,
			creditQuota: 0,
		});
		// The old client-side math (100 x max(5,3)) would render "300" here;
		// the backend's 0 must win, not silently fall back to it.
		expect(w.find(".pool-value").text()).toMatch(/^0\s+credits/);
	});
});
