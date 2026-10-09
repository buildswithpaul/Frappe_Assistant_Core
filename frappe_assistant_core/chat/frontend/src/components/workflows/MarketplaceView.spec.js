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

// Mirrors the server: featured_only narrows the set, category narrows what the
// store shows, and a page is capped at pageSize (the featured row asks for 6).
function serve(catalogue) {
	return async (category = null, _search = null, _sort = null, featuredOnly = false, _min = null, page = 0, pageSize = 20) => {
		let rows = catalogue;
		if (featuredOnly) rows = rows.filter((t) => t.featured);
		if (category) rows = rows.filter((t) => t.category === category);
		return { templates: rows.slice(page * pageSize, (page + 1) * pageSize), total: rows.length };
	};
}

function makeCatalogue(count, { featuredCount = 0, categories = ["Finance", "Inventory", "HR"] } = {}) {
	return Array.from({ length: count }, (_, i) => ({
		name: `t${i}`,
		template_name: `t${i}`,
		category: categories[i % categories.length],
		featured: i < featuredCount,
	}));
}

const MIXED = makeCatalogue(3, { featuredCount: 1 });
const ALL_FEATURED_8 = makeCatalogue(8, { featuredCount: 8 });
const NINE_OF_24 = makeCatalogue(24, { featuredCount: 9 });

async function mountWith(catalogue, { facetsFail = false } = {}) {
	const base = serve(catalogue);
	listTemplates.mockImplementation(async (...args) => {
		// The facet fetch is the only call that asks for a 100-row page.
		if (facetsFail && args[6] === 100) throw new Error("FAC Cloud unreachable");
		return base(...args);
	});
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

	it("hides the featured strip when all 8 templates are featured", async () => {
		// The featured fetch returns only 6, so a 6-vs-8 set comparison would wrongly show it.
		const w = await mountWith(ALL_FEATURED_8);
		expect(featuredShown(w)).toBe(false);
	});

	it("shows the featured strip when 9 of 24 templates are featured", async () => {
		// Regression guard: a partial featured set must keep the strip.
		const w = await mountWith(NINE_OF_24);
		expect(featuredShown(w)).toBe(true);
	});

	it("keeps the grid and shows only All when the facet fetch fails", async () => {
		const w = await mountWith(ALL_FEATURED_8, { facetsFail: true });
		expect(chipLabels(w)).toEqual(["All"]);
		expect(featuredShown(w)).toBe(true);
		expect(w.find(".marketplace-grid").exists()).toBe(true);
	});

	it("shows the featured strip again after selecting All", async () => {
		const w = await mountWith(MIXED);
		await w.findAll(".category-pills .pill").find((p) => p.text() === "All").trigger("click");
		await flushPromises();
		expect(featuredShown(w)).toBe(true);
	});
});
