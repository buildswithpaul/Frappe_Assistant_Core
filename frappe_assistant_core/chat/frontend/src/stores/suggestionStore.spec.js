import { describe, it, expect, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";

vi.mock("@/api/client", () => ({ api: { suggestions: { get: vi.fn() } } }));

import { api } from "@/api/client";
import { useSuggestionStore } from "./suggestionStore";

const CUSTOMER = { type: "Form", doctype: "Customer" };
const GENERAL = { type: "General" };

describe("suggestionStore.loadSuggestions", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		api.suggestions.get.mockReset();
	});

	it("returning to the loaded context discards a fetch started for a page in between", async () => {
		const store = useSuggestionStore();
		api.suggestions.get.mockResolvedValueOnce({
			suggestions: [{ name: "customer ask", source: "page" }],
		});
		await store.loadSuggestions(CUSTOMER);

		let resolveGeneral;
		api.suggestions.get.mockImplementationOnce(() => new Promise((r) => (resolveGeneral = r)));
		const general = store.loadSuggestions(GENERAL);
		await store.loadSuggestions(CUSTOMER);
		expect(store.isLoading).toBe(false);

		resolveGeneral({ suggestions: [{ name: "general starter", source: "default" }] });
		await general;
		expect(store.allSuggestions.map((s) => s.name)).toEqual(["customer ask"]);
		expect(api.suggestions.get).toHaveBeenCalledTimes(2);
	});
});
