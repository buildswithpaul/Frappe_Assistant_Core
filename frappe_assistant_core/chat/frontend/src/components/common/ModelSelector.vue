<template>
	<div class="model-selector" ref="selectorRef">
		<!-- Trigger Button -->
		<button
			@click="toggleDropdown"
			class="model-trigger"
			:disabled="modelStore.isLoading && !isOpen"
		>
			<svg class="model-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
				/>
			</svg>
			<span class="model-name">{{ modelStore.currentModelName }}</span>
			<svg
				class="chevron-icon"
				:class="{ open: isOpen }"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M19 9l-7 7-7-7"
				/>
			</svg>
		</button>

		<!-- Dropdown -->
		<Transition name="dropdown">
			<div v-if="isOpen" class="model-dropdown">
				<!-- Loading state -->
				<div v-if="modelStore.isLoading" class="dropdown-loading">
					<div class="loading-spinner"></div>
					<span>Loading models...</span>
				</div>

				<!-- Error state -->
				<div v-else-if="modelStore.error" class="dropdown-error">
					<span>{{ modelStore.error }}</span>
					<button @click="modelStore.loadModels()" class="retry-btn">Retry</button>
				</div>

				<!-- Models list -->
				<template v-else>
					<!-- Auto Mode Option (when enabled) -->
					<div v-if="modelStore.isAutoModeEnabled" class="auto-mode-section">
						<div
							class="model-option auto-option"
							:class="{ selected: modelStore.isAutoModeSelected }"
							@click="selectAutoMode"
						>
							<div class="model-info">
								<div class="auto-label">
									<svg
										class="auto-icon"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M13 10V3L4 14h7v7l9-11h-7z"
										/>
									</svg>
									<span class="model-label">Auto</span>
								</div>
								<span class="model-provider">{{
									modelStore.autoMode?.description ||
									"Automatically selects the best model"
								}}</span>
							</div>
							<svg
								v-if="modelStore.isAutoModeSelected"
								class="check-icon"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M5 13l4 4L19 7"
								/>
							</svg>
						</div>
					</div>

					<div v-for="tier in modelStore.orderedTiers" :key="tier" class="tier-group">
						<!-- Tier Header -->
						<div class="tier-header">
							<span class="tier-name">{{ tier }}</span>
						</div>

						<!-- Models in this tier -->
						<div
							v-for="model in modelStore.modelsByTier[tier]"
							:key="model.model_id"
							class="model-option"
							:class="{
								selected: model.model_id === modelStore.currentModelId,
								locked: !modelStore.isModelAccessible(model),
							}"
							@click="selectModel(model)"
						>
							<div class="model-info">
								<span class="model-label">{{ model.display_name }}</span>
								<span class="model-provider">{{ model.provider }}</span>
							</div>
							<span v-if="!modelStore.isModelAccessible(model)" class="lock-badge">
								Upgrade
							</span>
							<svg
								v-else-if="model.model_id === modelStore.currentModelId"
								class="check-icon"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M5 13l4 4L19 7"
								/>
							</svg>
						</div>
					</div>

					<!-- Empty state -->
					<div v-if="modelStore.orderedTiers.length === 0" class="dropdown-empty">
						No models available
					</div>
				</template>
			</div>
		</Transition>
	</div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useModelStore } from "@/stores/modelStore";

const modelStore = useModelStore();
const selectorRef = ref(null);
const isOpen = ref(false);

function toggleDropdown() {
	isOpen.value = !isOpen.value;
}

function closeDropdown() {
	isOpen.value = false;
}

function selectAutoMode() {
	// Don't re-select if already selected
	if (modelStore.isAutoModeSelected) {
		closeDropdown();
		return;
	}

	// Select auto mode
	modelStore.setSelectedModel("auto");
	closeDropdown();
}

function selectModel(model) {
	// Don't allow selecting locked models
	if (!modelStore.isModelAccessible(model)) {
		// Could emit event to open upgrade modal
		return;
	}

	// Don't re-select current model
	if (model.model_id === modelStore.currentModelId) {
		closeDropdown();
		return;
	}

	// Synchronous - just updates localStorage
	modelStore.setSelectedModel(model.model_id);
	closeDropdown();
}

// Click-away handler
function handleClickOutside(event) {
	if (selectorRef.value && !selectorRef.value.contains(event.target)) {
		closeDropdown();
	}
}

// Keyboard handler
function handleKeydown(event) {
	if (event.key === "Escape" && isOpen.value) {
		closeDropdown();
	}
}

onMounted(() => {
	document.addEventListener("click", handleClickOutside);
	document.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
	document.removeEventListener("click", handleClickOutside);
	document.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped>
.model-selector {
	position: relative;
}

.model-trigger {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
	max-width: 200px;
}

.model-trigger:hover {
	background-color: var(--ql-border);
}

.model-trigger:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}

.model-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
	color: var(--ql-text-muted);
}

.model-name {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.chevron-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
	color: var(--ql-text-muted);
	transition: transform 0.2s ease;
}

.chevron-icon.open {
	transform: rotate(180deg);
}

/* Dropdown */
.model-dropdown {
	position: absolute;
	top: calc(100% + 0.5rem);
	right: 0;
	min-width: 280px;
	max-height: 400px;
	overflow-y: auto;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
	z-index: 50;
}

/* Dropdown animation */
.dropdown-enter-active,
.dropdown-leave-active {
	transition: opacity 0.15s ease, transform 0.15s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
	opacity: 0;
	transform: translateY(-0.5rem);
}

/* Auto Mode Section */
.auto-mode-section {
	padding: 0.5rem 0;
	border-bottom: 1px solid var(--ql-border);
}

.auto-option {
	background: var(--ql-subtle);
}

.auto-option:hover {
	background: var(--ql-accent-soft);
}

.auto-option.selected {
	background: var(--ql-accent-soft);
}

.auto-label {
	display: flex;
	align-items: center;
	gap: 0.375rem;
}

.auto-icon {
	width: 1rem;
	height: 1rem;
	color: var(--ql-accent);
}

/* Tier groups */
.tier-group {
	padding: 0.5rem 0;
}

.tier-group:not(:last-child) {
	border-bottom: 1px solid var(--ql-border);
}

.tier-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.5rem 1rem;
}

.tier-name {
	font-size: 0.75rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.05em;
	color: var(--ql-text-muted);
}

/* Model options */
.model-option {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.625rem 1rem;
	cursor: pointer;
	transition: background-color 0.1s ease;
}

.model-option:hover:not(.locked) {
	background-color: var(--ql-subtle);
}

.model-option.selected {
	background-color: var(--ql-accent-soft);
}

.model-option.locked {
	opacity: 0.5;
	cursor: not-allowed;
}

.model-info {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
}

.model-label {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.model-provider {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.lock-badge {
	font-size: 0.75rem;
	font-weight: 500;
	padding: 0.25rem 0.5rem;
	background: var(--ql-accent);
	color: white;
	border-radius: 0.25rem;
}

.check-icon {
	width: 1.25rem;
	height: 1.25rem;
	color: var(--ql-accent);
}

/* Loading state */
.dropdown-loading {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
	padding: 2rem 1rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.loading-spinner {
	width: 1.5rem;
	height: 1.5rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* Error state */
.dropdown-error {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 0.75rem;
	padding: 1.5rem 1rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
	text-align: center;
}

.retry-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-accent);
	background: transparent;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.retry-btn:hover {
	background: var(--ql-accent);
	color: white;
}

/* Empty state */
.dropdown-empty {
	padding: 2rem 1rem;
	text-align: center;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

/* Mobile adjustments */
@media (max-width: 640px) {
	.model-trigger {
		max-width: 120px;
	}

	.model-name {
		display: none;
	}

	/* Fixed to the viewport, not the trigger. A 100vw panel anchored to
	   `right: 0` on a mid-bar button used to hang off the left edge. */
	.model-dropdown {
		position: fixed;
		top: calc(var(--ql-topbar-height, 56px) + 0.5rem);
		left: 1rem;
		right: 1rem;
		width: auto;
		min-width: 0;
		max-width: none;
		max-height: min(400px, calc(100dvh - var(--ql-topbar-height, 56px) - 1.5rem));
	}
}
</style>
