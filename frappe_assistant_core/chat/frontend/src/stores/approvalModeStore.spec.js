import { describe, it, expect, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: { approvalMode: { set: vi.fn(), acknowledge: vi.fn() } },
}));

import { api } from "@/api/client";
import { useApprovalModeStore } from "./approvalModeStore";

// What the server sends at start-up for a user who never chose, on a site whose FAC Cloud
// offers the mode.
const FRESH = { available: true, on: true, notice_seen: false };

describe("approvalModeStore", () => {
	let store;

	beforeEach(() => {
		setActivePinia(createPinia());
		api.approvalMode.set.mockReset();
		api.approvalMode.acknowledge.mockReset();
		store = useApprovalModeStore();
	});

	it("has no switch until the server says the mode is offered", () => {
		expect(store.available).toBe(false);
		expect(store.showNotice).toBe(false);
		expect(store.active).toBe(false);

		// A start-up answer from a site that could not use the chat carries no state at all.
		store.apply(undefined);
		expect(store.available).toBe(false);
	});

	it("is on for a user who never chose, and applies only once the notice was seen", async () => {
		store.apply(FRESH);
		expect(store.on).toBe(true);
		expect(store.showNotice).toBe(true);
		expect(store.active).toBe(false);

		api.approvalMode.acknowledge.mockResolvedValue({ ...FRESH, notice_seen: true });
		await store.acknowledge();

		expect(store.showNotice).toBe(false);
		expect(store.active).toBe(true);
	});

	it("saves a flip and shows what the server stored", async () => {
		store.apply({ ...FRESH, notice_seen: true });
		api.approvalMode.set.mockResolvedValue({ available: true, on: false, notice_seen: true });

		await store.setOn(false);

		expect(api.approvalMode.set).toHaveBeenCalledWith(false);
		expect(store.on).toBe(false);
		expect(store.active).toBe(false);
	});

	it("keeps the old state when a save fails", async () => {
		store.apply({ ...FRESH, notice_seen: true });
		api.approvalMode.set.mockRejectedValue(new Error("offline"));

		await store.setOn(false);

		expect(store.on).toBe(true);
		expect(store.saving).toBe(false);
	});
});
