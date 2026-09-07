import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { vi, describe, it, expect, beforeEach } from "vitest";
import PackContents from "@/components/settings/packs/PackContents.vue";
import { usePacksStore } from "@/stores/packsStore";

const PACK = {
	pack_id: "p1", display_name: "Healthcare Pack", acquisition: "purchased",
	description: "Clinical workflows", prompt_count: 2, skill_count: 1,
};

function mountCard() {
	return mount(PackContents, { props: { pack: PACK } });
}

describe("PackContents", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("renders the count line and description from the pack prop", () => {
		const w = mountCard();
		expect(w.text()).toContain("Healthcare Pack");
		expect(w.text()).toContain("Clinical workflows");
		expect(w.text()).toContain("2");
		expect(w.text()).toContain("prompt templates");
		expect(w.text()).toContain("1");
		expect(w.text()).toContain("skills");
	});

	it("loads contents once on expand and renders named rows", async () => {
		const store = usePacksStore();
		const spy = vi.spyOn(store, "loadContents").mockImplementation(async (id) => {
			store.contents = {
				[id]: {
					prompts: [{ prompt_id: "a", title: "Intake summary", category: "Clinical" }],
					skills: [{ skill_id: "s", title: "Record fetch", skill_type: "tool" }],
					loading: false, error: null,
				},
			};
		});
		const w = mountCard();
		await w.find(".pack-head").trigger("click");
		await flushPromises();
		expect(spy).toHaveBeenCalledWith("p1");
		expect(w.text()).toContain("Intake summary");
		expect(w.text()).toContain("Clinical");
		expect(w.text()).toContain("Record fetch");
		expect(w.text()).toContain("tool");

		await w.find(".pack-head").trigger("click"); // collapse
		await w.find(".pack-head").trigger("click"); // re-expand
		expect(spy).toHaveBeenCalledTimes(2);
	});

	it("shows the empty state when the pack has no prompts or skills", async () => {
		const store = usePacksStore();
		vi.spyOn(store, "loadContents").mockImplementation(async (id) => {
			store.contents = { [id]: { prompts: [], skills: [], loading: false, error: null } };
		});
		const w = mountCard();
		await w.find(".pack-head").trigger("click");
		await flushPromises();
		expect(w.text()).toContain("no prompts or skills yet");
	});
});
