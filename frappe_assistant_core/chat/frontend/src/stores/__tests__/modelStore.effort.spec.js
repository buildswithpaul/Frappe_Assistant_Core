import { describe, it, expect, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useModelStore } from "@/stores/modelStore";

const NEW = [
	{
		model_id: "a",
		tier: "Standard",
		tier_rank: 1,
		thinking_effective: true,
		reasoning_levels: ["off", "low", "medium", "high"],
		reasoning_off_floor: false,
	},
	{
		model_id: "b",
		tier: "Standard",
		tier_rank: 1,
		thinking_effective: true,
		reasoning_levels: ["off", "low", "medium", "high", "xhigh", "max"],
		reasoning_off_floor: true,
	},
];
const OLD = [{ model_id: "a", tier: "Standard", tier_rank: 1, thinking_effective: true }];

describe("modelStore effort levels", () => {
	beforeEach(() => setActivePinia(createPinia()));

	it("under auto offers every level any model accepts", () => {
		const store = useModelStore();
		store.models = NEW;
		store.selectedModel = "auto";
		expect(store.effortLevels).toEqual(["off", "low", "medium", "high", "xhigh", "max"]);
		expect(store.legacyMode).toBe(false);
	});

	it("a picked model lists every level and hints the ones it lacks", () => {
		const store = useModelStore();
		store.models = NEW;
		store.selectedModel = "a";
		expect(store.effortLevels).toEqual(["off", "low", "medium", "high", "xhigh", "max"]);
		expect(store.hintFor("max")).toBe("Runs at High on this model");
		expect(store.hintFor("medium")).toBeNull();
	});

	it("a picked model without levels offers only off", () => {
		const store = useModelStore();
		store.models = [...NEW, { model_id: "c", tier: "Standard", tier_rank: 1, reasoning_levels: [] }];
		store.selectedModel = "c";
		expect(store.effortLevels).toEqual(["off"]);
	});

	it("an AR without levels falls back to the legacy on/off control", () => {
		const store = useModelStore();
		store.models = OLD;
		store.selectedModel = "a";
		expect(store.legacyMode).toBe(true);
		expect(store.effortLevels).toEqual(["off", "high"]);
	});

	it("reports when off is a floor for the picked model", () => {
		const store = useModelStore();
		store.models = NEW;
		store.selectedModel = "b";
		expect(store.offFloor).toBe(true);
	});
});
