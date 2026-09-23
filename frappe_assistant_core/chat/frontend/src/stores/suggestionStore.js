import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { useTemplateStore } from "@/stores/templateStore";

export const useSuggestionStore = defineStore("suggestions", () => {
	const allSuggestions = ref([]);
	const isLoading = ref(false);
	const lastContextKey = ref(null);
	const suggestionsDisabled = ref(false);

	const hasSuggestions = computed(() => allSuggestions.value.length > 0);

	async function loadSuggestions(context = {}, { force = false } = {}) {
		// Avoid duplicate requests: skip if already loading or same context with data
		if (isLoading.value) return;
		const contextKey = JSON.stringify(context);
		if (!force && contextKey === lastContextKey.value && allSuggestions.value.length > 0) {
			return;
		}

		try {
			isLoading.value = true;
			lastContextKey.value = contextKey;

			const result = await api.suggestions.get(context);

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
		} catch (err) {
			logger.error("Failed to load suggestions:", err);
		} finally {
			isLoading.value = false;
		}
	}

	function clear() {
		allSuggestions.value = [];
		lastContextKey.value = null;
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
