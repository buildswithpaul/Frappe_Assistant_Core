import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

export const useTemplateStore = defineStore("templates", () => {
	// State
	const templates = ref([]);
	const categories = ref([]);
	const pinnedNames = ref([]);
	const isLoading = ref(false);
	const error = ref(null);
	const selectedCategory = ref("all");
	const searchQuery = ref("");

	// Category display names
	const categoryDisplayNames = {
		all: "All",
		"data-quality": "Data Quality",
		documentation: "Documentation",
		"sales-crm": "Sales & CRM",
		"hr-payroll": "HR & Payroll",
		purchasing: "Purchasing",
		manufacturing: "Manufacturing",
	};

	// Getters
	const pinnedTemplates = computed(() => {
		return templates.value.filter((t) => pinnedNames.value.includes(t.name));
	});

	const filteredTemplates = computed(() => {
		let filtered = templates.value;

		// Filter by category
		if (selectedCategory.value !== "all") {
			filtered = filtered.filter((t) => t.category === selectedCategory.value);
		}

		// Filter by search query
		if (searchQuery.value.trim()) {
			const query = searchQuery.value.toLowerCase();
			filtered = filtered.filter(
				(t) =>
					t.title?.toLowerCase().includes(query) ||
					t.description?.toLowerCase().includes(query) ||
					t.name?.toLowerCase().includes(query)
			);
		}

		return filtered;
	});

	const hasTemplates = computed(() => templates.value.length > 0);

	// Actions
	async function loadTemplates() {
		if (isLoading.value) return;

		try {
			isLoading.value = true;
			error.value = null;

			const result = await api.templates.getAll();

			if (result) {
				templates.value = result.templates || [];
				categories.value = result.categories || [];
				pinnedNames.value = result.pinned || [];
			}
		} catch (err) {
			error.value = err.message;
			logger.error("Failed to load templates:", err);
		} finally {
			isLoading.value = false;
		}
	}

	async function togglePin(templateName) {
		try {
			const isPinned = pinnedNames.value.includes(templateName);
			let newPinned;

			if (isPinned) {
				newPinned = pinnedNames.value.filter((n) => n !== templateName);
			} else {
				// Limit to 5 pinned
				if (pinnedNames.value.length >= 5) {
					error.value = "Maximum 5 templates can be pinned";
					setTimeout(() => {
						error.value = null;
					}, 3000);
					return false;
				}
				newPinned = [...pinnedNames.value, templateName];
			}

			const result = await api.templates.updatePinned(newPinned);

			if (result.success) {
				pinnedNames.value = result.pinned;
				return true;
			} else {
				error.value = result.error;
				return false;
			}
		} catch (err) {
			error.value = err.message;
			return false;
		}
	}

	function isPinned(templateName) {
		return pinnedNames.value.includes(templateName);
	}

	function getTemplateByName(name) {
		return templates.value.find((t) => t.name === name);
	}

	function setCategory(category) {
		selectedCategory.value = category;
	}

	function setSearchQuery(query) {
		searchQuery.value = query;
	}

	function clearError() {
		error.value = null;
	}

	function getCategoryDisplayName(category) {
		return categoryDisplayNames[category] || category;
	}

	/**
	 * Hydrate templates from suggestion response (avoids a separate AR call).
	 * Only populates if store is empty and not currently loading.
	 */
	function hydrateFromResponse(data) {
		if (isLoading.value || templates.value.length > 0) return;
		templates.value = data.templates || [];
		categories.value = data.categories || [];
		pinnedNames.value = data.pinned || [];
	}

	async function getRenderedPrompt(promptName, args = {}) {
		try {
			const result = await api.templates.getRendered(promptName, args);
			return result;
		} catch (err) {
			error.value = err.message;
			logger.error("Failed to get rendered prompt:", err);
			return null;
		}
	}

	return {
		// State
		templates,
		categories,
		pinnedNames,
		isLoading,
		error,
		selectedCategory,
		searchQuery,
		// Getters
		pinnedTemplates,
		filteredTemplates,
		hasTemplates,
		categoryDisplayNames,
		// Actions
		loadTemplates,
		hydrateFromResponse,
		togglePin,
		isPinned,
		getTemplateByName,
		setCategory,
		setSearchQuery,
		clearError,
		getCategoryDisplayName,
		getRenderedPrompt,
	};
});
