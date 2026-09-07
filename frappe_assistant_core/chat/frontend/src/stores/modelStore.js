import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";

// localStorage key for persisting user's model selection
const STORAGE_KEY = "faco_selected_model";

export const useModelStore = defineStore("models", () => {
	// State
	const models = ref([]);
	const modelsByTier = ref({});
	const selectedModel = ref(null); // User's selected model (from localStorage)
	const defaultModel = ref(null); // Tenant's default model (from AR)
	const maxTierRank = ref(999);
	const isLoading = ref(false);
	const error = ref(null);

	// Auto mode configuration from AR
	const autoMode = ref(null); // { enabled, description, model_id, fallback_chain_length }

	// Tier order for consistent display
	const tierOrder = ["Economy", "Standard", "Premium", "Reasoning"];

	// Getters

	// Check if auto mode is enabled (handles both boolean true and integer 1)
	const isAutoModeEnabled = computed(() => Boolean(autoMode.value?.enabled));

	// Check if user has selected auto mode
	const isAutoModeSelected = computed(() => selectedModel.value === "auto");

	// The model ID to use for API requests - selected or fallback to default
	const currentModelId = computed(() => selectedModel.value || defaultModel.value);

	// Get the full model object for the current selection
	// Returns null for auto mode since it dynamically selects
	const currentModel = computed(() => {
		if (isAutoModeSelected.value) return null;
		return models.value.find((m) => m.model_id === currentModelId.value);
	});

	// Display name for the current model
	const currentModelName = computed(() => {
		if (isAutoModeSelected.value) return "Auto";
		return currentModel.value?.display_name || "Select Model";
	});

	// Get ordered tiers (only those with models)
	const orderedTiers = computed(() =>
		tierOrder.filter((tier) => modelsByTier.value[tier]?.length > 0)
	);

	// Check if a model is accessible based on plan's max multiplier
	function isModelAccessible(model) {
		return model.tier_rank <= maxTierRank.value;
	}

	// Load selected model from localStorage
	function loadSelectedModel() {
		try {
			const stored = localStorage.getItem(STORAGE_KEY);
			if (stored) {
				selectedModel.value = stored;
			}
		} catch (e) {
			logger.warn("Failed to load model from localStorage:", e);
		}
	}

	// Save selected model to localStorage
	function saveSelectedModel(modelId) {
		try {
			if (modelId) {
				localStorage.setItem(STORAGE_KEY, modelId);
			} else {
				localStorage.removeItem(STORAGE_KEY);
			}
		} catch (e) {
			logger.warn("Failed to save model to localStorage:", e);
		}
	}

	// Actions

	// Set selected model (synchronous - just updates localStorage)
	function setSelectedModel(modelId) {
		// Special case: "auto" is always valid if auto mode is enabled
		if (modelId === "auto" && isAutoModeEnabled.value) {
			selectedModel.value = modelId;
			saveSelectedModel(modelId);
			return true;
		}

		// Validate that model exists and is accessible
		const model = models.value.find((m) => m.model_id === modelId);
		if (model && isModelAccessible(model)) {
			selectedModel.value = modelId;
			saveSelectedModel(modelId);
			return true;
		}
		return false;
	}

	// Clear selected model (reverts to default)
	function clearSelectedModel() {
		selectedModel.value = null;
		saveSelectedModel(null);
	}

	// Load available models from AR
	async function loadModels() {
		if (isLoading.value) return;

		try {
			isLoading.value = true;
			error.value = null;

			const result = await api.models.getAvailable();

			if (result && !result.error) {
				models.value = result.models || [];
				modelsByTier.value = result.models_by_tier || {};
				defaultModel.value = result.default_model;
				maxTierRank.value = result.max_tier_rank || 999;
				autoMode.value = result.auto_mode || null;

				// Load user's selection from localStorage
				loadSelectedModel();

				// Validate stored selection is still valid
				if (selectedModel.value) {
					// Special case: "auto" is valid if auto mode is enabled
					if (selectedModel.value === "auto" && isAutoModeEnabled.value) {
						// Keep auto mode selection
					} else if (selectedModel.value === "auto" && !isAutoModeEnabled.value) {
						// Auto mode was selected but is no longer available
						clearSelectedModel();
					} else {
						const storedModel = models.value.find(
							(m) => m.model_id === selectedModel.value
						);
						if (!storedModel || !isModelAccessible(storedModel)) {
							// Stored model no longer valid, clear it
							clearSelectedModel();
						}
					}
				}

				// Default to auto mode if enabled and no model selected
				if (!selectedModel.value && isAutoModeEnabled.value) {
					selectedModel.value = "auto";
					saveSelectedModel("auto");
				}
			} else {
				error.value = result?.error || "Failed to load models";
			}
		} catch (err) {
			error.value = err.message;
			logger.error("Failed to load models:", err);
		} finally {
			isLoading.value = false;
		}
	}

	function clearError() {
		error.value = null;
	}

	return {
		// State
		models,
		modelsByTier,
		selectedModel,
		defaultModel,
		maxTierRank,
		isLoading,
		error,
		autoMode,
		// Getters
		currentModelId,
		currentModel,
		currentModelName,
		orderedTiers,
		isAutoModeEnabled,
		isAutoModeSelected,
		// Methods
		isModelAccessible,
		setSelectedModel,
		clearSelectedModel,
		loadModels,
		clearError,
	};
});
