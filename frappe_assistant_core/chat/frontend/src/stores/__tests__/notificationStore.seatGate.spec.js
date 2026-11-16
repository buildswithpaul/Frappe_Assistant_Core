import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: { notifications: { get: vi.fn(), dismiss: vi.fn() } },
}));

import { api } from "@/api/client";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";

describe("notificationStore and the seat gate", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.useFakeTimers();
		api.notifications.get.mockReset().mockResolvedValue({ notifications: [], user: "a@x.com" });
	});
	afterEach(() => {
		useNotificationStore().stopPolling();
		vi.useRealTimers();
	});

	it.each(["checking", "not_registered", "no_role", "disabled", "error"])(
		"notification polling never starts for %s",
		async (status) => {
			useUserStore().registrationStatus = status;
			const store = useNotificationStore();
			store.startPolling();
			await store.refresh();
			await vi.advanceTimersByTimeAsync(600_000);
			expect(api.notifications.get).not.toHaveBeenCalled();
		}
	);

	it("polls once registration is ready", async () => {
		useUserStore().registrationStatus = "ready";
		const store = useNotificationStore();
		store.startPolling();
		await vi.advanceTimersByTimeAsync(0);
		expect(api.notifications.get).toHaveBeenCalledTimes(1);
	});

	it("a no_seat answer stops the timer", async () => {
		useUserStore().registrationStatus = "ready";
		api.notifications.get.mockResolvedValue({ notifications: [], user: "a@x.com", no_seat: true });
		const store = useNotificationStore();
		store.startPolling();
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(600_000);
		expect(api.notifications.get).toHaveBeenCalledTimes(1);
	});
});
