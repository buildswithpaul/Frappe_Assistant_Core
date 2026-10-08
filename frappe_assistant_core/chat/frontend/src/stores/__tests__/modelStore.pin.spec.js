import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

const getAvailable = vi.fn();
vi.mock("@/api/client", () => ({ api: { models: { getAvailable: (...a) => getAvailable(...a) } } }));

import { useModelStore } from "@/stores/modelStore";

const KEY = "faco_selected_model";
const payload = {
	models: [{ model_id: "gpt-saved", tier: "Standard", tier_rank: 1, display_name: "GPT" }],
	models_by_tier: { Standard: [{ model_id: "gpt-saved" }] },
	default_model: "gpt-saved",
	max_tier_rank: 3,
	auto_mode: { enabled: true },
};

/**
 * The Desk widget routes automatically. FAC Chat's saved choice belongs to FAC Chat: the widget must
 * neither be steered by it nor write to it. Production reaches this state when a person who picked a
 * model in FAC Chat opens the widget on Desk (same origin, same localStorage).
 */
describe("modelStore pin (widget)", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		getAvailable.mockReset().mockResolvedValue(payload);
	});

	it("keeps the pinned model over FAC Chat's saved one after the catalogue loads", async () => {
		localStorage.setItem(KEY, "gpt-saved");
		const store = useModelStore();
		store.pinModel("auto");
		await store.loadModels();
		expect(store.currentModelId).toBe("auto");
		expect(store.isAutoModeSelected).toBe(true);
		expect(localStorage.getItem(KEY)).toBe("gpt-saved");
	});

	it("does not clear FAC Chat's key when the saved model has been retired", async () => {
		localStorage.setItem(KEY, "retired-model");
		const store = useModelStore();
		store.pinModel("auto");
		await store.loadModels();
		expect(store.currentModelId).toBe("auto");
		expect(localStorage.getItem(KEY)).toBe("retired-model");
	});

	it("does not write a default when nothing was saved", async () => {
		const store = useModelStore();
		store.pinModel("auto");
		await store.loadModels();
		expect(localStorage.getItem(KEY)).toBeNull();
	});

	it("ignores set/clear while pinned", () => {
		const store = useModelStore();
		store.pinModel("auto");
		store.models = payload.models;
		store.setSelectedModel("gpt-saved");
		store.clearSelectedModel();
		expect(store.currentModelId).toBe("auto");
		expect(localStorage.getItem(KEY)).toBeNull();
	});

	it("is inert for FAC Chat, which never pins", async () => {
		localStorage.setItem(KEY, "gpt-saved");
		const store = useModelStore();
		await store.loadModels();
		expect(store.currentModelId).toBe("gpt-saved");
		localStorage.setItem(KEY, "retired-model");
		const again = useModelStore();
		again.selectedModel = null;
		again.isLoading = false;
		await again.loadModels();
		expect(localStorage.getItem(KEY)).toBe("auto");
	});
});
