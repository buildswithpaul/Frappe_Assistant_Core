import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getHome = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		home: { get: (...a) => getHome(...a) },
		workflows: { listRuns: vi.fn().mockResolvedValue({ runs: [] }), list: vi.fn() },
	},
}));

import { useHomeSignals } from "./useHomeSignals";

const items = ["a", "b", "c", "d"].map((id) => ({ id, tone: "warning", source: "S", count: 1, title: id }));

function run(cap) {
	let state;
	const C = defineComponent({
		setup() {
			state = useHomeSignals({ cap });
			return () => null;
		},
	});
	mount(C);
	return state;
}

describe("useHomeSignals", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		getHome.mockReset();
		vi.stubGlobal("requestAnimationFrame", (cb) => cb());
	});

	it("loads after paint and applies the reactive cap", async () => {
		getHome.mockResolvedValue({ lens_label: "Sales", area: "Selling", company: "X", items });
		const cap = ref(2);
		const s = run(cap);
		await flushPromises();
		expect(s.loaded.value).toBe(true);
		expect(s.failed.value).toBe(false);
		expect(s.items.value.map((i) => i.id)).toEqual(["a", "b"]);
		cap.value = 3;
		expect(s.items.value).toHaveLength(3);
		expect(s.lens.value).toBe("Sales");
	});

	it("marks failed without throwing", async () => {
		getHome.mockRejectedValue(new Error("boom"));
		const s = run(ref(3));
		await flushPromises();
		expect(s.failed.value).toBe(true);
		expect(s.items.value).toEqual([]);
	});
});
