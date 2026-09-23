import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useLayoutStore } from "@/stores/layoutStore";

describe("layoutStore", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("starts closed", () => {
		expect(useLayoutStore().drawerOpen).toBe(false);
	});

	it("open/close/toggle mutate drawerOpen", () => {
		const s = useLayoutStore();
		s.openDrawer();
		expect(s.drawerOpen).toBe(true);
		s.closeDrawer();
		expect(s.drawerOpen).toBe(false);
		s.toggleDrawer();
		expect(s.drawerOpen).toBe(true);
		s.toggleDrawer();
		expect(s.drawerOpen).toBe(false);
	});
});
