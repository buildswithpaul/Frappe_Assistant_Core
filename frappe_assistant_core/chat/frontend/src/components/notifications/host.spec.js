import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: { notifications: { get: vi.fn().mockResolvedValue({ notifications: [], user: "a@x.com" }) , dismiss: vi.fn() } },
}));
import NotificationHost from "@/components/notifications/NotificationHost.vue";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";

describe("NotificationHost", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("starts polling on mount and stops on unmount", async () => {
		const store = useNotificationStore();
		const start = vi.spyOn(store, "startPolling");
		const stop = vi.spyOn(store, "stopPolling");
		const w = mount(NotificationHost);
		expect(start).toHaveBeenCalled();
		w.unmount();
		expect(stop).toHaveBeenCalled();
	});

	it("hides HighPriorityBanner during onboarding, keeps OutageBanner", async () => {
		const userStore = useUserStore();
		userStore.registrationStatus = "not_registered";
		const w = mount(NotificationHost);
		expect(w.findComponent({ name: "HighPriorityBanner" }).exists()).toBe(false);
		expect(w.findComponent({ name: "OutageBanner" }).exists()).toBe(true);
	});
});
