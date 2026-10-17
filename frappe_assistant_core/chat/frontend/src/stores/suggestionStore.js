import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { useTemplateStore } from "@/stores/templateStore";

export const useSuggestionStore = defineStore("suggestions", () => {
	const allSuggestions = ref([]);
	const isLoading = ref(false);
	// The context whose suggestions are in allSuggestions; set only after a successful load.
	const lastContextKey = ref(null);
	// The context currently being fetched, so a newer one can supersede it.
	let inFlightKey = null;
	const suggestionsDisabled = ref(false);

	const hasSuggestions = computed(() => allSuggestions.value.length > 0);

	async function loadSuggestions(context = {}, { force = false } = {}) {
		const contextKey = JSON.stringify(context);
		// Avoid duplicate requests: skip the same context while it loads or once it has data.
		// A different context supersedes the one in flight (Desk navigation).
		if (isLoading.value && contextKey === inFlightKey) return;
		if (!force && contextKey === lastContextKey.value && allSuggestions.value.length > 0) {
			// Back on the loaded context: a fetch started for a page in between is now stale.
			inFlightKey = null;
			isLoading.value = false;
			return;
		}

		try {
			isLoading.value = true;
			inFlightKey = contextKey;

			const result = await api.suggestions.get(context);
			if (contextKey !== inFlightKey) return;

			// Response is now { suggestions: [...], templates: {...} }
			// Fall back to flat array for backward compatibility
			if (result && result.suggestions) {
				allSuggestions.value = result.suggestions;
				// Hydrate templateStore from the same response (avoids a separate AR call)
				if (result.templates) {
					const templateStore = useTemplateStore();
					templateStore.hydrateFromResponse(result.templates);
				}
			} else {
				allSuggestions.value = result || [];
			}
			suggestionsDisabled.value = Boolean(result?.suggestions_disabled);
			lastContextKey.value = contextKey;
		} catch (err) {
			logger.error("Failed to load suggestions:", err);
			// The previous page's asks must not outlive a failed fetch for this one, and
			// returning to the previous context must fetch again.
			if (contextKey === inFlightKey) {
				lastContextKey.value = null;
				allSuggestions.value = allSuggestions.value.filter((s) => s.source !== "page");
			}
		} finally {
			if (contextKey === inFlightKey) isLoading.value = false;
		}
	}

	function clear() {
		allSuggestions.value = [];
		lastContextKey.value = null;
		inFlightKey = null;
	}

	return {
		allSuggestions,
		isLoading,
		suggestionsDisabled,
		hasSuggestions,
		loadSuggestions,
		clear,
	};
});
