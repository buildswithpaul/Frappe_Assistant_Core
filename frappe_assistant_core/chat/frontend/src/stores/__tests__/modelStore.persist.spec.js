import { describe, it, expect, beforeEach, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { setActivePinia, createPinia } from "pinia";

const getAvailable = vi.fn();
const setSelected = vi.fn();
vi.mock("@/api/client", () => ({
	api: {
		models: {
			getAvailable: (...a) => getAvailable(...a),
			setSelected: (...a) => setSelected(...a),
		},
	},
}));

import { useModelStore } from "@/stores/modelStore";

const KEY = "faco_selected_model";
const payload = (selected = "") => ({
	models: [
		{ model_id: "gpt-saved", tier: "Standard", tier_rank: 1, display_name: "GPT" },
		{ model_id: "claude-other", tier: "Standard", tier_rank: 1, display_name: "Claude" },
	],
	models_by_tier: { Standard: [{ model_id: "gpt-saved" }, { model_id: "claude-other" }] },
	default_model: "claude-other",
	max_tier_rank: 3,
	auto_mode: { enabled: true },
	selected_model: selected,
});

describe("modelStore persistence", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		getAvailable.mockReset();
		setSelected.mockReset().mockResolvedValue({ success: true });
	});

	it("server choice wins over localStorage", async () => {
		// a second browser has a stale localStorage (another model), so only the server row carries the choice
		localStorage.setItem(KEY, "claude-other");
		getAvailable.mockResolvedValue(payload("gpt-saved"));
		const store = useModelStore();
		await store.loadModels();
		expect(store.currentModelId).toBe("gpt-saved");
		expect(localStorage.getItem(KEY)).toBe("gpt-saved");
		expect(setSelected).not.toHaveBeenCalled();
	});

	it("a fresh browser picks up the server choice with an empty localStorage", async () => {
		// a second browser has an empty localStorage, so only the server row carries the choice
		getAvailable.mockResolvedValue(payload("gpt-saved"));
		const store = useModelStore();
		await store.loadModels();
		expect(store.currentModelId).toBe("gpt-saved");
	});

	it("localStorage-only value is uploaded once", async () => {
		// production reaches this when a user chose a model before the server row existed
		localStorage.setItem(KEY, "gpt-saved");
		getAvailable.mockResolvedValue(payload(""));
		const store = useModelStore();
		await store.loadModels();
		expect(store.currentModelId).toBe("gpt-saved");
		expect(setSelected).toHaveBeenCalledTimes(1);
		expect(setSelected).toHaveBeenCalledWith("gpt-saved");

		getAvailable.mockResolvedValue(payload("gpt-saved"));
		await store.loadModels();
		expect(setSelected).toHaveBeenCalledTimes(1);
	});

	it("missing model at load does not overwrite the server choice", async () => {
		// production reaches this when the saved model is briefly absent from the list
		// (a health-excluded or briefly disabled provider) while the server row still holds it
		getAvailable.mockResolvedValue({ ...payload("gpt-saved"), models: [payload().models[1]] });
		const store = useModelStore();
		await store.loadModels();
		expect(store.currentModelId).toBe("auto");
		expect(setSelected).not.toHaveBeenCalled();

		getAvailable.mockResolvedValue(payload("gpt-saved"));
		const next = useModelStore();
		next.isLoading = false;
		await next.loadModels();
		expect(next.currentModelId).toBe("gpt-saved");
	});

	it("setSelectedModel posts the choice", async () => {
		getAvailable.mockResolvedValue(payload("gpt-saved"));
		const store = useModelStore();
		await store.loadModels();
		expect(store.setSelectedModel("claude-other")).toBe(true);
		expect(setSelected).toHaveBeenCalledWith("claude-other");
		expect(localStorage.getItem(KEY)).toBe("claude-other");
	});

	it("an unusable choice is not posted", async () => {
		getAvailable.mockResolvedValue(payload("gpt-saved"));
		const store = useModelStore();
		await store.loadModels();
		expect(store.setSelectedModel("not-a-model")).toBe(false);
		expect(setSelected).not.toHaveBeenCalled();
	});

	it("clearSelectedModel clears the server row", async () => {
		getAvailable.mockResolvedValue(payload("gpt-saved"));
		const store = useModelStore();
		await store.loadModels();
		store.clearSelectedModel();
		expect(setSelected).toHaveBeenLastCalledWith("");
	});

	it("a failed save does not break the picker", async () => {
		getAvailable.mockResolvedValue(payload("gpt-saved"));
		setSelected.mockRejectedValue(new Error("offline"));
		const store = useModelStore();
		await store.loadModels();
		expect(store.setSelectedModel("claude-other")).toBe(true);
		await Promise.resolve();
		expect(store.currentModelId).toBe("claude-other");
	});

	it("pinModel writes neither store", () => {
		const store = useModelStore();
		store.pinModel("auto");
		expect(localStorage.getItem(KEY)).toBeNull();
		expect(setSelected).not.toHaveBeenCalled();
	});
});

describe("the Desk widget follows the server-side choice", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		localStorage.clear();
		getAvailable.mockReset();
		setSelected.mockReset().mockResolvedValue({ success: true });
	});

	it("widget uses the server-side choice in a fresh browser", async () => {
		// a second browser has an empty localStorage, so only the server row carries the choice
		getAvailable.mockResolvedValue(payload("gpt-saved"));
		const store = useModelStore();
		store.pinModel("auto");
		await store.loadModels();
		expect(store.currentModelId).toBe("gpt-saved");
		expect(localStorage.getItem(KEY)).toBeNull();
		expect(setSelected).not.toHaveBeenCalled();
	});

	it("stays on auto when the server has no choice or a retired one", async () => {
		getAvailable.mockResolvedValue(payload("retired-model"));
		const store = useModelStore();
		store.pinModel("auto");
		await store.loadModels();
		expect(store.currentModelId).toBe("auto");
	});

	it("sends the store's model on every turn, not a fixed one", () => {
		const source = readFileSync(resolve(process.cwd(), "src/widget/panel/WidgetPanel.vue"), "utf8");
		expect(source).toContain("modelStore.currentModelId");
	});
});
