import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import MyAgentsSection from "@/components/workflows/list/MyAgentsSection.vue";

setActivePinia(createPinia());

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
});
