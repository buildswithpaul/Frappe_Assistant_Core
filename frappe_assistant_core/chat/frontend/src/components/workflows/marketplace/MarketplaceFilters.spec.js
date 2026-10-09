import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import MarketplaceFilters from "./MarketplaceFilters.vue";

vi.mock("@/utils/i18n", () => ({ __: (text) => `xx:${text}` }));

const categories = [
	{ value: "All", label: "All" },
	{ value: "Finance", label: "Finance" },
];

describe("MarketplaceFilters", () => {
	it("translates its UI literals", () => {
		const w = mount(MarketplaceFilters, {
			props: { categories, searchQuery: "", categoryFilter: null, sortBy: "" },
		});
		expect(w.find(".marketplace-title").text()).toBe("xx:Template Marketplace");
		expect(w.find(".search-input").attributes("placeholder")).toBe("xx:Search templates...");
		expect(w.findAll(".sort-select option").map((o) => o.text())).toEqual([
			"xx:Popular",
			"xx:Top Rated",
			"xx:Recent",
			"xx:Featured",
		]);
	});

	it("renders each chip's label verbatim and emits its value", async () => {
		// The view translates the "All" label before passing it in.
		const w = mount(MarketplaceFilters, {
			props: { categories, searchQuery: "", categoryFilter: null, sortBy: "" },
		});
		const pills = w.findAll(".pill");
		expect(pills.map((p) => p.text())).toEqual(["All", "Finance"]);
		await pills[1].trigger("click");
		expect(w.emitted("update:categoryFilter")[0]).toEqual(["Finance"]);
	});
});
