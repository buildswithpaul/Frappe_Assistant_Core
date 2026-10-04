import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { useModelStore } from "@/stores/modelStore";
import ThinkingLevelMenu from "../ThinkingLevelMenu.vue";

const ALL = ["off", "low", "medium", "high", "xhigh", "max"];

function mountMenu(props = {}) {
	return mount(ThinkingLevelMenu, {
		props: { open: true, levels: ALL, selected: "off", legacy: false, offFloor: false, hintFor: () => null, ...props },
	});
}

describe("ThinkingLevelMenu", () => {
	it("lists every level with its label", () => {
		const labels = mountMenu().findAll("[role=menuitemradio]").map((b) => b.find(".level-label").text());
		expect(labels).toEqual(["Off", "Low", "Medium", "High", "Extra high", "Max"]);
	});

	it("marks the selected level and emits a new choice", async () => {
		const wrapper = mountMenu({ selected: "high" });
		expect(wrapper.find("[aria-checked=true] .level-label").text()).toBe("High");
		await wrapper.findAll("[role=menuitemradio]")[5].trigger("click");
		expect(wrapper.emitted("select")[0]).toEqual(["max"]);
		expect(wrapper.emitted("close")).toBeTruthy();
	});

	it("says higher levels cost more", () => {
		const wrapper = mountMenu();
		expect(wrapper.text()).toContain("Higher levels think longer and use more credits.");
		const tagged = wrapper.findAll(".level-cost").map((t) => t.text());
		expect(tagged).toEqual(["uses more credits", "uses more credits"]);
	});

	it("shows the step-down hint for a level the model lacks", () => {
		const wrapper = mountMenu({ hintFor: (l) => (l === "max" ? "Runs at High on this model" : null) });
		expect(wrapper.text()).toContain("Runs at High on this model");
	});

	it("renders the step-down hint for Max on a model that tops out at High", () => {
		setActivePinia(createPinia());
		const store = useModelStore();
		store.models = [
			{ model_id: "a", tier: "Standard", tier_rank: 1, reasoning_levels: ["off", "low", "medium", "high"] },
		];
		store.selectedModel = "a";
		const wrapper = mountMenu({ levels: store.effortLevels, hintFor: store.hintFor });
		const max = wrapper.findAll("[role=menuitemradio]")[5];
		expect(max.text()).toContain("Runs at High on this model");
	});

	it("legacy mode shows Off and On only", () => {
		const labels = mountMenu({ legacy: true, levels: ["off", "high"] })
			.findAll("[role=menuitemradio] .level-label").map((b) => b.text());
		expect(labels).toEqual(["Off", "On"]);
	});

	it("explains when off still thinks a little", () => {
		expect(mountMenu({ offFloor: true }).text()).toContain("This model always thinks a little");
	});

	it("closes on an outside click and on Escape, but not on its trigger", () => {
		const wrapper = mount(ThinkingLevelMenu, {
			attachTo: document.body,
			props: { open: true, levels: ALL, selected: "off", hintFor: () => null },
		});
		const trigger = document.createElement("button");
		trigger.setAttribute("data-thinking-trigger", "");
		document.body.appendChild(trigger);
		trigger.click();
		expect(wrapper.emitted("close")).toBeFalsy();
		document.body.click();
		expect(wrapper.emitted("close")).toHaveLength(1);
		document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
		expect(wrapper.emitted("close")).toHaveLength(2);
		trigger.remove();
		wrapper.unmount();
	});
});
