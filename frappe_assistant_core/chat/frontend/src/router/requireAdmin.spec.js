import { describe, it, expect, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: { user: { getCurrent: vi.fn() } },
}));

import { api } from "@/api/client";
import { requireAdmin } from "@/router";
import { useUserStore } from "@/stores/userStore";

/** Resolve on a later tick, the way a real request does. */
function slowly(value) {
	return () => new Promise((resolve) => setTimeout(() => resolve(value), 0));
}

describe("requireAdmin", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		api.user.getCurrent.mockReset();
	});

	it("waits for the store before deciding", async () => {
		// The bug: guards run before App.vue mounts, so on a cold load `isAdmin`
		// is still its initial false. Every admin route bounced to Profile —
		// invisible when these pages were only reached by in-app navigation,
		// and plainly wrong on the deep link the customer returns to after
		// paying.
		api.user.getCurrent.mockImplementation(
			slowly({ user: "paul@example.com", is_admin: true, status: "ready" }),
		);
		const next = vi.fn();

		await requireAdmin({ path: "/settings/billing" }, {}, next);

		expect(next).toHaveBeenCalledTimes(1);
		expect(next).toHaveBeenCalledWith();
	});

	it("still turns a non-admin away", async () => {
		api.user.getCurrent.mockImplementation(
			slowly({ user: "member@example.com", is_admin: false, status: "ready" }),
		);
		const next = vi.fn();

		await requireAdmin({ path: "/settings/billing" }, {}, next);

		expect(next).toHaveBeenCalledWith("/settings/profile");
	});

	it("does not re-fetch when the store is already populated", async () => {
		api.user.getCurrent.mockResolvedValue({
			user: "paul@example.com",
			is_admin: true,
			status: "ready",
		});
		const store = useUserStore();
		await store.loadUser();
		api.user.getCurrent.mockClear();

		await requireAdmin({ path: "/settings/billing" }, {}, vi.fn());

		expect(api.user.getCurrent).not.toHaveBeenCalled();
	});

	it("shares one request when several guards run at once", async () => {
		api.user.getCurrent.mockImplementation(
			slowly({ user: "paul@example.com", is_admin: true, status: "ready" }),
		);

		await Promise.all([
			requireAdmin({}, {}, vi.fn()),
			requireAdmin({}, {}, vi.fn()),
			requireAdmin({}, {}, vi.fn()),
		]);

		expect(api.user.getCurrent).toHaveBeenCalledTimes(1);
	});
});
