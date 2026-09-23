import { describe, it, expect, vi, beforeEach } from "vitest";
import { ref } from "vue";

vi.mock("@/api/client", () => ({
	api: {
		users: {
			getAvailableUsers: vi.fn(),
			addUser: vi.fn(),
			inviteUser: vi.fn(),
			list: vi.fn(),
		},
		billing: {
			previewSeatCharge: vi.fn(),
		},
	},
}));

vi.mock("@/composables/_billing/hostedCheckout", () => ({
	startHostedCheckout: vi.fn().mockResolvedValue(undefined),
}));

import { api } from "@/api/client";
import { startHostedCheckout } from "@/composables/_billing/hostedCheckout";
import { useAddUserFlow } from "@/composables/useAddUserFlow.js";

function harness(limitValue) {
	const ctx = {
		userLimit: ref(limitValue),
		actionError: ref(""),
		successMessage: ref(""),
		clearMessageAfterDelay: vi.fn(),
		refreshUsers: vi.fn(),
		refreshLimit: vi.fn(),
	};
	return { ctx, flow: useAddUserFlow(ctx) };
}

describe("useAddUserFlow seat-purchase preview", () => {
	beforeEach(() => {
		startHostedCheckout.mockClear();
		api.billing.previewSeatCharge.mockReset();
		api.billing.previewSeatCharge.mockResolvedValue({
			success: true,
			pricing: {
				prorated_rate: 66.63,
				tax: 0,
				total: 66.63,
				days_remaining: 20,
				days_in_cycle: 30,
				currency: "INR",
				per_user_price: 1999,
				tax_rate_percent: 0,
				components: [],
				credits_per_user: 500,
				credits_granted: 333,
			},
		});
	});

	it("promises next month's renewal off the paid seat count, not the member count", async () => {
		// The production case: 9 paid, 5 assigned, no vacant seat to fill --
		// so adding one more triggers the prorated charge, and the modal's
		// renewal promise must say 10 (9 paid + 1), not 6 (5 assigned + 1).
		const { ctx, flow } = harness({
			is_per_user: true,
			paid_seats: 9,
			active_users: 5,
			vacant_seats: 0,
			min_users: 3,
			remaining: 100,
			is_unlimited: false,
		});

		await flow.startInvite({ user_id: "new@example.com", full_name: "New User" }, "Member");

		expect(ctx.actionError.value).toBe("");
		expect(flow.seatPurchaseConfirm.value.newSeatCount).toBe(10);
	});

	it("refuses to open the modal while the renewal is unpaid", async () => {
		// A stalled renewal pins current_period_end in the past, so the
		// proration is zero days and the seat quotes at 0.00. AR sends no
		// pricing at all in that case and refuses the purchase, so opening
		// the modal would offer a free seat the next click cannot buy.
		api.billing.previewSeatCharge.mockResolvedValue({
			success: true,
			pricing: {
				renewal_outstanding: true,
				invoice: "AR-INV-2026-00232",
				blocked_reason: "Your last renewal payment hasn't gone through yet.",
			},
		});
		const { ctx, flow } = harness({
			is_per_user: true,
			paid_seats: 3,
			active_users: 3,
			vacant_seats: 0,
			min_users: 1,
			remaining: 100,
			is_unlimited: false,
		});

		await flow.startInvite({ user_id: "sarah@example.com", full_name: "Sarah" }, "Member");

		expect(flow.seatPurchaseConfirm.value).toBeNull();
		expect(ctx.actionError.value).toBe(
			"Your last renewal payment hasn't gone through yet.",
		);
	});

	it("falls back to active_users + 1 when the backend hasn't sent paid_seats", async () => {
		const { flow } = harness({
			is_per_user: true,
			active_users: 4,
			vacant_seats: 0,
			min_users: 3,
			remaining: 100,
			is_unlimited: false,
		});

		await flow.startInvite({ user_id: "new@example.com", full_name: "New User" }, "Member");

		expect(flow.seatPurchaseConfirm.value.newSeatCount).toBe(5);
	});

	it("never sends invited_by from the browser -- AR stamps it from the verified session", async () => {
		const { flow } = harness({
			is_per_user: true,
			paid_seats: 9,
			active_users: 5,
			vacant_seats: 0,
			min_users: 3,
			remaining: 100,
			is_unlimited: false,
		});

		await flow.startInvite({ user_id: "new@example.com", full_name: "New User" }, "Member");
		await flow.confirmAddUser();

		expect(startHostedCheckout).toHaveBeenCalledTimes(1);
		const [purpose, params] = startHostedCheckout.mock.calls[0];
		expect(purpose).toBe("Seat");
		expect(params.user_id).toBe("new@example.com");
		expect(params).not.toHaveProperty("invited_by");
	});
});

describe("useAddUserFlow post-payment finalize", () => {
	beforeEach(() => {
		api.users.inviteUser.mockReset();
		api.users.list.mockReset();
		localStorage.clear();
		window.history.pushState({}, "", "/settings/users");
	});

	function seedStripeReturn(pending) {
		localStorage.setItem("faco_seat_pending", JSON.stringify(pending));
		window.history.pushState({}, "", "/settings/users?seat_purchase=1&session_id=cs_test_1");
	}

	// This is the regression: AR's payment handler (ensure_seat_member)
	// already created the member when the charge settled. The browser's own
	// finalize call is racing that -- not failing -- so a duplicate-member
	// result from commitUser must read as success here.
	it("reports success and refreshes when the finalize call races AR's own seat creation", async () => {
		const { ctx, flow } = harness(null);
		seedStripeReturn({ user_id: "bob@example.com", full_name: "Bob", userRole: "Member" });

		api.users.inviteUser.mockResolvedValue({
			success: false,
			error: "bob@example.com is already a member or has a pending invite.",
		});
		api.users.list.mockResolvedValue({
			users: [{ user_id: "bob@example.com", status: "Pending" }],
		});

		await flow.handleStripeSeatReturn();

		expect(ctx.successMessage.value).toBe("Bob invited successfully");
		expect(ctx.actionError.value).toBe("");
		expect(ctx.refreshUsers).toHaveBeenCalledTimes(1);
		expect(ctx.refreshLimit).toHaveBeenCalledTimes(1);
	});

	// Contrast case: an ordinary invite (no payment involved, plenty of
	// vacant seats so no Stripe round-trip ever happens) must still treat
	// "already a member" as the real conflict it is -- the narrowing above
	// must not leak into this path.
	it("still surfaces a genuine already-a-member conflict as an error on the ordinary invite path", async () => {
		const { ctx, flow } = harness({
			is_per_user: true,
			vacant_seats: 1,
			active_users: 5,
			min_users: 3,
			remaining: 100,
			is_unlimited: false,
		});

		api.users.inviteUser.mockResolvedValue({
			success: false,
			error: "bob@example.com is already a member or has a pending invite.",
		});

		await flow.startInvite({ user_id: "bob@example.com", full_name: "Bob" }, "Member");

		expect(ctx.actionError.value).toBe(
			"bob@example.com is already a member or has a pending invite.",
		);
		expect(ctx.successMessage.value).toBe("");
		expect(api.users.list).not.toHaveBeenCalled();
		expect(ctx.refreshUsers).not.toHaveBeenCalled();
		expect(ctx.refreshLimit).not.toHaveBeenCalled();
	});
});
