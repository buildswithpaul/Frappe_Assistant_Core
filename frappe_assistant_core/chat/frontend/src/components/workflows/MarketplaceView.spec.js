import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

const { listTemplates } = vi.hoisted(() => ({ listTemplates: vi.fn() }));

vi.mock("@/api/client", () => ({
	api: {
		workflows: {
			listTemplates,
			getCreatorStats: vi.fn().mockResolvedValue({ templates_published: 0 }),
		},
	},
}));

import MarketplaceView from "./MarketplaceView.vue";

// Mirrors the server: featured_only narrows the set, and category narrows the
// list the store shows. The facet fetch passes no category, so it sees all.
function serve(catalogue) {
	return async (category = null, search = null, _sort = null, featuredOnly = false) => {
		let rows = catalogue;
		if (featuredOnly) rows = rows.filter((t) => t.is_featured);
		if (category) rows = rows.filter((t) => t.category === category);
		return { templates: rows, total: rows.length };
	};
}

const MIXED = [
	{ name: "t1", template_name: "t1", category: "Finance", is_featured: true },
	{ name: "t2", template_name: "t2", category: "Inventory", is_featured: false },
	{ name: "t3", template_name: "t3", category: "HR", is_featured: false },
];

const ALL_FEATURED = MIXED.map((t) => ({ ...t, is_featured: true }));

async function mountWith(catalogue) {
	listTemplates.mockImplementation(serve(catalogue));
	const wrapper = mount(MarketplaceView, { global: { plugins: [createPinia()] } });
	// Mount fires the list, featured and facet fetches; the dynamic imports settle later than flushPromises.
	await vi.waitFor(() => expect(listTemplates).toHaveBeenCalledTimes(3));
	await flushPromises();
	return wrapper;
}

function chipLabels(wrapper) {
	return wrapper.findAll(".category-pills .pill").map((p) => p.text());
}

function featuredShown(wrapper) {
	return wrapper.find(".featured-section").exists();
}

describe("MarketplaceView facets", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		listTemplates.mockReset();
	});

	it("lists the catalogue's categories instead of a fixed list", async () => {
		const w = await mountWith(MIXED);
		expect(chipLabels(w)).toEqual(["All", "Finance", "HR", "Inventory"]);
	});

	it("keeps the other categories when one is selected", async () => {
		// Regression guard for the trap: the store holds only the filtered list,
		// so the chips must come from the unfiltered facet fetch.
		const w = await mountWith(MIXED);
		await w.findAll(".category-pills .pill").find((p) => p.text() === "HR").trigger("click");
		await flushPromises();
		expect(chipLabels(w)).toEqual(["All", "Finance", "HR", "Inventory"]);
	});

	it("hides the featured strip when every template is featured", async () => {
		const w = await mountWith(ALL_FEATURED);
		expect(featuredShown(w)).toBe(false);
	});

	it("shows the featured strip when some templates are not featured", async () => {
		const w = await mountWith(MIXED);
		expect(featuredShown(w)).toBe(true);
	});

	it("shows the featured strip again after selecting All", async () => {
		const w = await mountWith(MIXED);
		await w.findAll(".category-pills .pill").find((p) => p.text() === "All").trigger("click");
		await flushPromises();
		expect(featuredShown(w)).toBe(true);
	});
});
