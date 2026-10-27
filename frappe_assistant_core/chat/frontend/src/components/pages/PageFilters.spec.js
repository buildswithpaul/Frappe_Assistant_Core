import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import PageFilters from "./PageFilters.vue";

const mountFilters = (counts, modelValue = "all") =>
	mount(PageFilters, { props: { counts, modelValue } });

describe("PageFilters", () => {
	it("shows each pill with its count in a labelled group", () => {
		const w = mountFilters({ all: 4, mine: 2, shared: 2, drafts: 1 });
		expect(w.find("[role=group]").attributes("aria-label")).toBe("Show");
		expect(w.findAll("button").map((b) => b.text())).toEqual(["All 4", "Only you 2", "Shared 2", "Drafts 1"]);
	});

	it("hides every pill with no pages except All", () => {
		const w = mountFilters({ all: 2, mine: 0, shared: 2, drafts: 0 });
		expect(w.findAll("button").map((b) => b.text())).toEqual(["All 2", "Shared 2"]);
		expect(mountFilters({ all: 0, mine: 0, shared: 0, drafts: 0 }).findAll("button")).toHaveLength(1);
	});

	it("marks the selected pill with aria-pressed", () => {
		const w = mountFilters({ all: 4, mine: 2, shared: 2, drafts: 1 }, "shared");
		expect(w.findAll("button").map((b) => b.attributes("aria-pressed"))).toEqual([
			"false",
			"false",
			"true",
			"false",
		]);
	});

	it("emits the chosen filter", async () => {
		const w = mountFilters({ all: 4, mine: 2, shared: 2, drafts: 1 });
		await w.findAll("button")[3].trigger("click");
		expect(w.emitted("update:modelValue")).toEqual([["drafts"]]);
	});
});
