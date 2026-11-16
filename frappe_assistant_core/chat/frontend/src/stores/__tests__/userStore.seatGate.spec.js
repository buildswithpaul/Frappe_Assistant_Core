import { describe, it, expect, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: { users: { getMyCreditStatus: vi.fn() } },
}));

import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";

const SEATED = { has_individual_limit: true, monthly_credit_limit: 100, credits_used_this_month: 7 };

describe("userStore credit status and the seat gate", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		api.users.getMyCreditStatus.mockReset();
	});

	it("does not call getMyCreditStatus before registration is ready", async () => {
		const store = useUserStore();
		// registrationStatus starts at "checking" and moves on only once the access check answers.
		for (const status of ["checking", "not_registered", "no_role", "disabled", "error"]) {
			store.registrationStatus = status;
			await store.loadMyCreditStatus();
		}
		expect(api.users.getMyCreditStatus).not.toHaveBeenCalled();
	});

	it("keeps a seated user's figure", async () => {
		const store = useUserStore();
		store.registrationStatus = "ready";
		api.users.getMyCreditStatus.mockResolvedValue(SEATED);
		await store.loadMyCreditStatus();
		expect(store.myCreditStatus).toEqual(SEATED);
	});

	it.each([[{ no_seat: true }], [{ unavailable: true }]])("treats %o as no figure", async (reply) => {
		const store = useUserStore();
		store.registrationStatus = "ready";
		store.myCreditStatus = SEATED;
		api.users.getMyCreditStatus.mockResolvedValue(reply);
		await store.loadMyCreditStatus();
		expect(store.myCreditStatus).toBeNull();
	});

	it("keeps stale: true when the backend says so", async () => {
		const store = useUserStore();
		store.registrationStatus = "ready";
		api.users.getMyCreditStatus.mockResolvedValue({ ...SEATED, stale: true });
		await store.loadMyCreditStatus();
		expect(store.myCreditStatus.stale).toBe(true);
	});
});
