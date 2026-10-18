import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { defineComponent, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getHome = vi.fn();
const hideSignal = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		home: { get: (...a) => getHome(...a), hideSignal: (...a) => hideSignal(...a) },
		workflows: { listRuns: vi.fn().mockResolvedValue({ runs: [] }), list: vi.fn() },
	},
}));

import { useHomeSignals } from "./useHomeSignals";
import { useUserStore } from "@/stores/userStore";
import { api } from "@/api/client";

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
		hideSignal.mockReset();
		vi.stubGlobal("requestAnimationFrame", (cb) => {
			cb();
			return 1;
		});
		vi.stubGlobal("cancelAnimationFrame", vi.fn());
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
		expect(s.lensLabel.value).toBe("Sales");
	});

	it("marks failed without throwing", async () => {
		getHome.mockRejectedValue(new Error("boom"));
		const s = run(ref(3));
		await flushPromises();
		expect(s.failed.value).toBe(true);
		expect(s.items.value).toEqual([]);
	});

	it("a payload with needs_you_enabled false disables the section", async () => {
		getHome.mockResolvedValue({ needs_you_enabled: false, items: [] });
		const s = run(ref(3));
		await flushPromises();
		expect(s.enabled.value).toBe(false);
	});

	it("is enabled when the payload says nothing", async () => {
		getHome.mockResolvedValue({ items });
		const s = run(ref(3));
		await flushPromises();
		expect(s.enabled.value).toBe(true);
	});

	it("caps at the payload's needs_you_count, never above the caller's cap", async () => {
		getHome.mockResolvedValue({ items, needs_you_count: 1 });
		const s = run(ref(3));
		await flushPromises();
		expect(s.items.value.map((i) => i.id)).toEqual(["a"]);
		getHome.mockResolvedValue({ items, needs_you_count: 3 });
		const t = run(ref(2));
		await flushPromises();
		expect(t.items.value).toHaveLength(2);
	});

	it("drops server items named in hidden_signals", async () => {
		getHome.mockResolvedValue({ items, hidden_signals: ["a"] });
		const s = run(ref(3));
		await flushPromises();
		expect(s.items.value.map((i) => i.id)).toEqual(["b", "c", "d"]);
	});

	it("hide removes the card at once and keeps it removed when the request succeeds", async () => {
		getHome.mockResolvedValue({ items });
		let finish;
		hideSignal.mockReturnValue(new Promise((resolve) => (finish = resolve)));
		const s = run(ref(3));
		await flushPromises();
		const pending = s.hide("a");
		expect(s.items.value.map((i) => i.id)).toEqual(["b", "c", "d"]);
		finish({ hidden_signals: ["a"] });
		await pending;
		expect(hideSignal).toHaveBeenCalledWith("a");
		expect(s.items.value.map((i) => i.id)).toEqual(["b", "c", "d"]);
	});

	it("hide restores the card when the request fails", async () => {
		getHome.mockResolvedValue({ items });
		hideSignal.mockRejectedValue(new Error("boom"));
		const s = run(ref(3));
		await flushPromises();
		await s.hide("a");
		expect(s.items.value.map((i) => i.id)).toEqual(["a", "b", "c"]);
		expect(s.hideFailed.value).toBe(true);
	});

	describe("failed workflows attention item", () => {
		beforeEach(() => {
			useUserStore().workflowsEnabled = true;
			api.workflows.listRuns.mockResolvedValue({
				runs: [{ workflow: "WF-1", started_at: new Date().toISOString() }],
			});
			api.workflows.list = vi.fn().mockResolvedValue({ workflows: [] });
			localStorage.clear();
		});

		it("shows by default", async () => {
			getHome.mockResolvedValue({ items: [] });
			const s = run(ref(3));
			await flushPromises();
			expect(s.items.value.map((i) => i.id)).toEqual(["failed_workflows"]);
		});

		it("is dropped from the merge when hidden_signals names it", async () => {
			getHome.mockResolvedValue({ items: [], hidden_signals: ["failed_workflows"] });
			const s = run(ref(3));
			await flushPromises();
			expect(s.items.value).toEqual([]);
		});

		it("hide removes it optimistically", async () => {
			getHome.mockResolvedValue({ items: [] });
			hideSignal.mockResolvedValue({ hidden_signals: ["failed_workflows"] });
			const s = run(ref(3));
			await flushPromises();
			await s.hide("failed_workflows");
			expect(s.items.value).toEqual([]);
		});
	});
});
