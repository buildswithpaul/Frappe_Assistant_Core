import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import MyAgentsSection from "@/components/workflows/list/MyAgentsSection.vue";

setActivePinia(createPinia());

// jsdom has no ResizeObserver; ListPageShell observes its width.
globalThis.ResizeObserver ??= class {
	observe() {}
	disconnect() {}
	unobserve() {}
};

const base = {
	workflows: [],
	isLoading: false,
	error: null,
	total: 0,
	statusFilter: null,
	currentPage: 0,
	pageSize: 20,
	isAdmin: true,
};

describe("MyAgentsSection", () => {
	it("shows an outage with Retry, not the 'No agents yet' empty state", async () => {
		const w = mount(MyAgentsSection, { props: { ...base, error: "FAC Cloud down" } });
		expect(w.text()).toContain("FAC Cloud down");
		expect(w.text()).not.toContain("No agents yet");
		await w.get('[role="alert"] button').trigger("click");
		expect(w.emitted("retry")).toHaveLength(1);
	});

	// regression guard: the empty state was already correct before this change
	it("shows the empty state when the list really is empty", () => {
		const w = mount(MyAgentsSection, { props: base });
		expect(w.text()).toContain("No agents yet");
	});

	it("renders the singular and plural stat", () => {
		const one = mount(MyAgentsSection, {
			props: { ...base, workflows: [{ name: "A", workflow_name: "A" }], total: 1 },
		});
		expect(one.text()).toContain("1 agent · 1 total");
		const two = mount(MyAgentsSection, {
			props: {
				...base,
				workflows: [
					{ name: "A", workflow_name: "A" },
					{ name: "B", workflow_name: "B" },
				],
				total: 2,
			},
		});
		expect(two.text()).toContain("2 agents · 2 total");
	});
});
