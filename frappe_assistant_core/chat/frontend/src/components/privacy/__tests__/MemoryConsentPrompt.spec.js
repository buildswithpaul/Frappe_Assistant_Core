import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/client", () => ({
	api: { privacy: { confirmMemoryConsent: vi.fn() } },
}));

vi.mock("@/utils/logger", () => ({
	logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}));

import { api } from "@/api/client";
import { useUserStore } from "@/stores/userStore";
import MemoryConsentPrompt from "../MemoryConsentPrompt.vue";

// initialize_spa sets both: memoryEnabled from AR capabilities, userAuthStatus from
// get_user_auth_status, which carries AR's memory_consent_pending flag.
function mountWith({ memory = true, pending = true } = {}) {
	const store = useUserStore();
	store.memoryEnabled = memory;
	store.userAuthStatus = { ready: true, memory_consent_pending: pending };
	return { wrapper: mount(MemoryConsentPrompt, { attachTo: document.body }), store };
}

function button(wrapper, label) {
	return wrapper.findAll("button").find((b) => b.text().trim() === label);
}

describe("MemoryConsentPrompt", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		api.privacy.confirmMemoryConsent.mockReset();
	});

	it("asks only when AR reports consent pending and memory exists", () => {
		expect(mountWith().wrapper.find("[role=dialog]").exists()).toBe(true);
		expect(mountWith({ pending: false }).wrapper.find("[role=dialog]").exists()).toBe(false);
		expect(mountWith({ memory: false }).wrapper.find("[role=dialog]").exists()).toBe(false);
	});

	it("keeping memory sends keep=true and closes", async () => {
		api.privacy.confirmMemoryConsent.mockResolvedValue({ memory_consent: true });
		const { wrapper, store } = mountWith();

		await button(wrapper, "Keep memory on").trigger("click");
		await flushPromises();

		expect(api.privacy.confirmMemoryConsent).toHaveBeenCalledWith(true);
		expect(store.memoryConsentPending).toBe(false);
		expect(wrapper.find("[role=dialog]").exists()).toBe(false);
	});

	it("turning memory off sends keep=false", async () => {
		api.privacy.confirmMemoryConsent.mockResolvedValue({ memory_consent: false });
		const { wrapper } = mountWith();

		await button(wrapper, "Turn off and delete memories").trigger("click");
		await flushPromises();

		expect(api.privacy.confirmMemoryConsent).toHaveBeenCalledWith(false);
		expect(wrapper.find("[role=dialog]").exists()).toBe(false);
	});

	it("stays open with an error when saving fails", async () => {
		api.privacy.confirmMemoryConsent.mockRejectedValue(new Error("AR down"));
		const { wrapper, store } = mountWith();

		await button(wrapper, "Keep memory on").trigger("click");
		await flushPromises();

		expect(wrapper.find("[role=alert]").exists()).toBe(true);
		expect(store.memoryConsentPending).toBe(true);
	});

	it("deciding later hides it without answering", async () => {
		const { wrapper, store } = mountWith();

		await button(wrapper, "Decide later").trigger("click");

		expect(wrapper.find("[role=dialog]").exists()).toBe(false);
		expect(api.privacy.confirmMemoryConsent).not.toHaveBeenCalled();
		expect(store.memoryConsentPending).toBe(true);
	});
});
