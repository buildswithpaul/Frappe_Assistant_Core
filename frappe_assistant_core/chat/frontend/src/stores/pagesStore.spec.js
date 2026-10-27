import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const listPages = vi.fn();
vi.mock("@/api/domains/facPage", () => ({ facPage: { listPages: (...a) => listPages(...a) } }));
vi.mock("@/utils/logger", () => ({ logger: { error: vi.fn() } }));

import { usePagePanel } from "@/composables/usePagePanel";
import { usePagesStore } from "./pagesStore";

let pinia;
beforeEach(() => {
	pinia = createPinia();
	setActivePinia(pinia);
	usePagePanel().chips.value = [];
	listPages.mockReset().mockResolvedValue([{ name: "a", title: "A" }]);
});

// The store's watcher lives on the shared chips singleton, so each test's store is stopped.
afterEach(() => {
	usePagesStore().$dispose();
	usePagePanel().chips.value = [];
});

describe("pagesStore", () => {
	it("loads once however often ensureLoaded is called", async () => {
		const store = usePagesStore();
		await Promise.all([store.ensureLoaded(), store.ensureLoaded()]);
		await store.ensureLoaded();
		expect(listPages).toHaveBeenCalledOnce();
		expect(store.hasPages).toBe(true);
		expect(store.loaded).toBe(true);
	});

	it("fails soft: no pages, an error, and not loaded", async () => {
		listPages.mockRejectedValue(new Error("down"));
		const store = usePagesStore();
		await store.load();
		expect(store.pages).toEqual([]);
		expect(store.hasPages).toBe(false);
		expect(store.error).toBe(true);
		expect(store.loaded).toBe(false);
	});

	it("keeps the earlier list when a reload fails", async () => {
		const store = usePagesStore();
		await store.load();
		listPages.mockRejectedValue(new Error("down"));
		await store.load();
		expect(store.pages).toEqual([{ name: "a", title: "A" }]);
		expect(store.error).toBe(true);
	});

	it("ensureLoaded tries again after a failure, and clears the error on success", async () => {
		listPages.mockRejectedValueOnce(new Error("down"));
		const store = usePagesStore();
		await store.ensureLoaded();
		await store.ensureLoaded();
		expect(listPages).toHaveBeenCalledTimes(2);
		expect(store.error).toBe(false);
		expect(store.loaded).toBe(true);
	});

	it("ignores an older response that arrives after a newer one", async () => {
		let resolveOld;
		listPages.mockReturnValueOnce(new Promise((resolve) => (resolveOld = resolve)));
		const store = usePagesStore();
		const old = store.load();
		listPages.mockResolvedValueOnce([{ name: "new", title: "New" }]);
		await store.load();
		resolveOld([{ name: "old", title: "Old" }]);
		await old;
		expect(store.pages).toEqual([{ name: "new", title: "New" }]);
	});

	it("reloads when a page write lands in chat after the first load", async () => {
		const store = usePagesStore();
		await store.load();
		usePagePanel().chips.value = [{ name: "x", version: 2 }];
		await nextTick();
		expect(listPages).toHaveBeenCalledTimes(2);
	});

	it("does not load on a chip change before the first load", async () => {
		usePagesStore();
		usePagePanel().chips.value = [{ name: "x", version: 2 }];
		await nextTick();
		expect(listPages).not.toHaveBeenCalled();
	});
});
