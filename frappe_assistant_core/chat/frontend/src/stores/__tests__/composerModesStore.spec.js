import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useComposerModesStore } from "@/stores/composerModesStore";

describe("composerModesStore", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
	});

	it("defaults both modes to off", () => {
		const store = useComposerModesStore();
		expect(store.modesFor("s1")).toEqual({ webSearch: false, thinking: false });
	});

	it("keeps modes separate per session", () => {
		const store = useComposerModesStore();
		store.toggle("s1", "webSearch");
		expect(store.modesFor("s1").webSearch).toBe(true);
		expect(store.modesFor("s2").webSearch).toBe(false);
	});

	it("survives a store rebuild", () => {
		useComposerModesStore().toggle("s1", "thinking");
		setActivePinia(createPinia());
		expect(useComposerModesStore().modesFor("s1").thinking).toBe(true);
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
