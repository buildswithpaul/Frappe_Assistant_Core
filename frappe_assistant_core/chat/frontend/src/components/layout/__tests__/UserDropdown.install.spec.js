import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { ref } from "vue";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

const canInstall = ref(false);
const needsInstructions = ref(false);
const promptInstall = vi.fn();
vi.mock("@/composables/usePwaInstall", () => ({
	usePwaInstall: () => ({ canInstall, needsInstructions, promptInstall }),
}));
const showToast = vi.fn();
vi.mock("@/composables/useToast", () => ({ useToast: () => ({ showToast }) }));

import UserDropdown from "@/components/layout/UserDropdown.vue";

beforeAll(() => {
	window.__ = (s) => s;
});

beforeEach(() => {
	setActivePinia(createPinia());
	vi.clearAllMocks();
	canInstall.value = false;
	needsInstructions.value = false;
});

async function openMenu() {
	const w = mount(UserDropdown, { global: { plugins: [createPinia()] } });
	await w.get("[data-test=user-avatar]").trigger("click");
	return w;
}

describe("UserDropdown install item", () => {
	it("is hidden when the app cannot be installed", async () => {
		const w = await openMenu();
		expect(w.find("[data-test=install-app]").exists()).toBe(false);
	});

	it("shows the browser's install prompt", async () => {
		canInstall.value = true;
		const w = await openMenu();
		await w.get("[data-test=install-app]").trigger("click");
		expect(promptInstall).toHaveBeenCalledTimes(1);
		expect(showToast).not.toHaveBeenCalled();
		expect(w.find(".user-dropdown-menu").exists()).toBe(false);
	});

	it("explains Add to Home Screen where there is no prompt (iPhone, iPad)", async () => {
		canInstall.value = true;
		needsInstructions.value = true;
		const w = await openMenu();
		await w.get("[data-test=install-app]").trigger("click");
		expect(promptInstall).not.toHaveBeenCalled();
		expect(showToast).toHaveBeenCalledWith("To install, tap Share, then Add to Home Screen.", "info", 6000);
	});
});
