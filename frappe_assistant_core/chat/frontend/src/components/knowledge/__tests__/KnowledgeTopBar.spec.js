import { describe, it, expect, beforeAll, vi } from "vitest";
import { ref, computed } from "vue";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import KnowledgeTopBar from "@/components/knowledge/KnowledgeTopBar.vue";

const drawerWidth = vi.hoisted(() => ({ value: false }));
const toggleDrawer = vi.hoisted(() => vi.fn());
vi.mock("@/composables/useNavToggle", () => ({
	useNavToggle: () => ({
		isMobile: ref(false),
		isDrawerWidth: computed(() => drawerWidth.value),
		onHamburger: () => toggleDrawer(),
	}),
}));

beforeAll(() => {
	window.__ = (s) => s;
	setActivePinia(createPinia());
});

const mountBar = () => mount(KnowledgeTopBar, { global: { stubs: { StorageBar: true } } });

describe("KnowledgeTopBar hamburger", () => {
	it("is hidden at desktop width, where there is no panel to toggle", () => {
		drawerWidth.value = false;
		expect(mountBar().find(".sidebar-toggle-btn").exists()).toBe(false);
	});

	it("opens the drawer at drawer width", async () => {
		drawerWidth.value = true;
		const w = mountBar();
		await w.find(".sidebar-toggle-btn").trigger("click");
		expect(toggleDrawer).toHaveBeenCalledTimes(1);
		expect(w.emitted("toggle-sidebar")).toBeUndefined();
	});
});
