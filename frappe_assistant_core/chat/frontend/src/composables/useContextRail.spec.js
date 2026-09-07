import { describe, it, expect } from "vitest";
import { defineComponent, ref, nextTick, h } from "vue";
import { mount } from "@vue/test-utils";
import {
	resolveRailMode,
	useContextRail,
	RAIL_WIDE_MIN,
	RAIL_TAB_MIN,
} from "@/composables/useContextRail.js";

describe("resolveRailMode", () => {
	it("is hidden whenever there are no artifacts, regardless of width", () => {
		expect(resolveRailMode(1920, false)).toBe("hidden");
		expect(resolveRailMode(1000, false)).toBe("hidden");
		expect(resolveRailMode(500, false)).toBe("hidden");
	});

	it("docks the rail at and above the wide breakpoint", () => {
		expect(resolveRailMode(RAIL_WIDE_MIN, true)).toBe("rail");
		expect(resolveRailMode(1920, true)).toBe("rail");
	});

	it("uses a tab between tab and wide breakpoints", () => {
		expect(resolveRailMode(RAIL_WIDE_MIN - 1, true)).toBe("tab"); // 1279
		expect(resolveRailMode(1024, true)).toBe("tab");
		expect(resolveRailMode(RAIL_TAB_MIN, true)).toBe("tab"); // 768
	});

	it("uses a bottom sheet below the tab breakpoint", () => {
		expect(resolveRailMode(RAIL_TAB_MIN - 1, true)).toBe("sheet"); // 767
		expect(resolveRailMode(375, true)).toBe("sheet");
	});
});

// Mount helper: runs the composable inside a real component so onMounted fires.
function mountRail(hasArtifacts, width) {
	if (width != null) {
		window.innerWidth = width;
	}
	let api;
	const Comp = defineComponent({
		setup() {
			api = useContextRail(hasArtifacts);
			return () => h("div");
		},
	});
	const wrapper = mount(Comp);
	return { api, wrapper };
}

describe("useContextRail", () => {
	it("docked rail is visible without opening", () => {
		const { api } = mountRail(ref(true), 1920);
		expect(api.mode.value).toBe("rail");
		expect(api.isVisible.value).toBe(true);
		expect(api.showAffordance.value).toBe(false);
	});

	it("tab mode is hidden until opened, then visible", async () => {
		const { api } = mountRail(ref(true), 1100);
		expect(api.mode.value).toBe("tab");
		expect(api.showAffordance.value).toBe(true);
		expect(api.isVisible.value).toBe(false);
		api.open();
		await nextTick();
		expect(api.isVisible.value).toBe(true);
		api.close();
		await nextTick();
		expect(api.isVisible.value).toBe(false);
	});

	it("sheet mode toggles open/closed", async () => {
		const { api } = mountRail(ref(true), 600);
		expect(api.mode.value).toBe("sheet");
		api.toggle();
		await nextTick();
		expect(api.isVisible.value).toBe(true);
		api.toggle();
		await nextTick();
		expect(api.isVisible.value).toBe(false);
	});

	it("auto-hides when artifacts disappear", async () => {
		const has = ref(true);
		const { api } = mountRail(has, 1920);
		expect(api.isVisible.value).toBe(true);
		has.value = false;
		await nextTick();
		expect(api.mode.value).toBe("hidden");
		expect(api.isVisible.value).toBe(false);
	});

	it("collapses and reopens the docked rail", async () => {
		const { api } = mountRail(ref(true), 1920);
		expect(api.mode.value).toBe("rail");
		expect(api.isVisible.value).toBe(true);
		expect(api.showDockReopen.value).toBe(false);

		api.collapseDock();
		await nextTick();
		expect(api.isVisible.value).toBe(false);
		expect(api.showDockReopen.value).toBe(true);

		api.expandDock();
		await nextTick();
		expect(api.isVisible.value).toBe(true);
		expect(api.showDockReopen.value).toBe(false);
	});

	it("a new turn's artifacts re-show a collapsed docked rail", async () => {
		const has = ref(true);
		const { api } = mountRail(has, 1920);
		api.collapseDock();
		await nextTick();
		expect(api.isVisible.value).toBe(false);

		// turn ends with no artifacts, then a new turn produces some
		has.value = false;
		await nextTick();
		has.value = true;
		await nextTick();
		expect(api.isVisible.value).toBe(true);
		expect(api.showDockReopen.value).toBe(false);
	});

	it("resizing into docked mode clears a stale open flag", async () => {
		const { api } = mountRail(ref(true), 1100);
		api.open();
		await nextTick();
		expect(api.isVisible.value).toBe(true);
		window.innerWidth = 1920;
		window.dispatchEvent(new Event("resize"));
		await nextTick();
		expect(api.mode.value).toBe("rail");
		expect(api.isOpen.value).toBe(false);
		expect(api.isVisible.value).toBe(true);
	});
});
