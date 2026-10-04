import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/api/client";
import { logger } from "@/utils/logger";
import { EFFORT_LEVELS, LEVEL_LABELS } from "@/stores/composerModesStore";

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
	const pickerOpen = ref(false);

	// Auto mode configuration from AR
	const autoMode = ref(null); // { enabled, description, model_id, fallback_chain_length }

	// Tier order for consistent display
	const tierOrder = ["Economy", "Standard", "Premium"];

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

	// Whether the Thinking toggle can actually be honoured right now. Under
	// auto, the model isn't picked yet, so it's honoured if ANY reachable
	// model can do it; with an explicit model, it's that model's own flag.
	// AR sets `thinking_effective` false-closed (operator flag AND a real
	// parameter shape AND enough output-token headroom), so a lit pill here
	// always means the toggle will do something.
	const thinkingHonoured = computed(() => {
		if (isAutoModeSelected.value) {
			return models.value.some(
				(m) => m.thinking_effective && isModelAccessible(m)
			);
		}
		return Boolean(currentModel.value?.thinking_effective);
	});

	const ORDER = EFFORT_LEVELS;

	// An AR that predates the selector publishes no reasoning_levels. Then the
	// composer keeps the old on/off control, and "on" travels as thinking_enabled.
	const legacyMode = computed(() => !models.value.some((m) => Array.isArray(m.reasoning_levels)));

	const effortLevels = computed(() => {
		if (legacyMode.value) return thinkingHonoured.value ? ["off", "high"] : ["off"];
		if (!isAutoModeSelected.value) {
			// Unsupported levels stay listed; hintFor says where they actually run.
			return currentModel.value?.reasoning_levels?.length ? [...ORDER] : ["off"];
		}
		const offered = new Set(models.value.filter(isModelAccessible).flatMap((m) => m.reasoning_levels || []));
		return ORDER.filter((level) => offered.has(level));
	});

	// Under auto every level is enabled (the model is not chosen yet); for a
	// picked model, a level it does not accept runs at the nearest lower one.
	function hintFor(level) {
		if (legacyMode.value || isAutoModeSelected.value || level === "off") return null;
		const accepted = currentModel.value?.reasoning_levels || [];
		if (accepted.includes(level) || accepted.length <= 1) return null;
		const rank = ORDER.indexOf(level);
		const lower = accepted.filter((l) => l !== "off" && ORDER.indexOf(l) < rank);
		const runsAt = lower.length ? lower[lower.length - 1] : accepted.find((l) => l !== "off");
		return runsAt ? `Runs at ${LEVEL_LABELS[runsAt]} on this model` : null;
	}

	const offFloor = computed(
		() => !isAutoModeSelected.value && Boolean(currentModel.value?.reasoning_off_floor)
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

	// The receipt carries a model id; every routing surface wants the name a
	// person recognises. Null when the catalogue has not loaded or the model
	// is no longer offered — callers fall back to the id.
	function modelDisplayName(modelId) {
		if (!modelId) return null;
		return models.value.find((m) => m.model_id === modelId)?.display_name || null;
	}

	function openPicker() {
		pickerOpen.value = true;
	}

	function closePicker() {
		pickerOpen.value = false;
	}

	return {
		// State
		pickerOpen,
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
		thinkingHonoured,
		effortLevels,
		legacyMode,
		offFloor,
		hintFor,
		// Methods
		isModelAccessible,
		modelDisplayName,
		setSelectedModel,
		clearSelectedModel,
		loadModels,
		clearError,
		openPicker,
		closePicker,
	};
});
