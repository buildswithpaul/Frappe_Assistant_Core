import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useComposerModesStore } from "@/stores/composerModesStore";

describe("composerModesStore", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
	});

	it("defaults web search off and thinking to off", () => {
		const store = useComposerModesStore();
		expect(store.modesFor("s1")).toEqual({ webSearch: false, effort: "off" });
	});

	it("sets a thinking level per session", () => {
		const store = useComposerModesStore();
		store.setEffort("s1", "xhigh");
		expect(store.modesFor("s1").effort).toBe("xhigh");
		expect(store.modesFor("s2").effort).toBe("off");
	});

	it("ignores an unknown level", () => {
		const store = useComposerModesStore();
		store.setEffort("s1", "turbo");
		expect(store.modesFor("s1").effort).toBe("off");
	});

	it("migrates a saved boolean from before the selector", () => {
		localStorage.setItem(
			"faco_composer_modes",
			JSON.stringify({ s1: { thinking: true }, s2: { thinking: false } })
		);
		const store = useComposerModesStore();
		expect(store.modesFor("s1").effort).toBe("high");
		expect(store.modesFor("s2").effort).toBe("off");
	});

	it("the legacy on/off toggle flips between off and high", () => {
		const store = useComposerModesStore();
		store.toggle("s1", "thinking");
		expect(store.modesFor("s1").effort).toBe("high");
		store.toggle("s1", "thinking");
		expect(store.modesFor("s1").effort).toBe("off");
	});

	it("keeps modes separate per session", () => {
		const store = useComposerModesStore();
		store.toggle("s1", "webSearch");
		expect(store.modesFor("s1").webSearch).toBe(true);
		expect(store.modesFor("s2").webSearch).toBe(false);
	});

	it("survives a store rebuild", () => {
		useComposerModesStore().setEffort("s1", "high");
		setActivePinia(createPinia());
		expect(useComposerModesStore().modesFor("s1").effort).toBe("high");
	});

	it("migrates modes chosen before the session existed", () => {
		const store = useComposerModesStore();
		store.toggle(null, "webSearch");
		store.adoptPendingSession("s-new");
		expect(store.modesFor("s-new").webSearch).toBe(true);
	});

	it("prunes to the 50 most recent sessions", () => {
		const store = useComposerModesStore();
		for (let i = 0; i < 55; i++) store.toggle(`s${i}`, "webSearch");
		expect(Object.keys(store.bySession).length).toBeLessThanOrEqual(50);
		expect(store.modesFor("s54").webSearch).toBe(true);
	});
});
