import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

vi.mock("@/api/client", () => ({
	api: { notifications: { get: vi.fn().mockResolvedValue({ notifications: [], user: "a@x.com" }), dismiss: vi.fn() } },
}));

import { api } from "@/api/client";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUserStore } from "@/stores/userStore";
import NotificationHost from "./NotificationHost.vue";

describe("NotificationHost polling", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		api.notifications.get.mockClear();
	});

	it("starts polling when the registration status becomes ready after mount", async () => {
		// A tenant owner finishing Connect, or an invited user activated by first use, reaches ready mid-session.
		const user = useUserStore();
		user.registrationStatus = "not_registered";
		const wrapper = mount(NotificationHost, { global: { stubs: { OutageBanner: true, HighPriorityBanner: true } } });
		await nextTick();
		expect(api.notifications.get).not.toHaveBeenCalled();
		user.registrationStatus = "ready";
		await nextTick();
		await nextTick();
		expect(api.notifications.get).toHaveBeenCalledTimes(1);
		useNotificationStore().stopPolling();
		wrapper.unmount();
	});
});
