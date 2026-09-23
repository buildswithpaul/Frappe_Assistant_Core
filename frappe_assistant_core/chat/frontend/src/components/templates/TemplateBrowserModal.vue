<template>
	<Teleport to="body">
		<div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
			<div class="modal-container">
				<!-- Header -->
				<div class="modal-header">
					<h2 class="modal-title">Quick Prompts</h2>
					<button @click="$emit('close')" class="close-btn" aria-label="Close">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M6 18L18 6M6 6l12 12"
							/>
						</svg>
					</button>
				</div>

				<!-- Search and Filter -->
				<div class="modal-filters">
					<div class="search-wrapper">
						<svg
							class="search-icon"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
							/>
						</svg>
						<input
							v-model="searchQuery"
							type="text"
							placeholder="Search prompts..."
							class="search-input"
						/>
					</div>
					<div class="category-filter">
						<button
							v-for="category in allCategories"
							:key="category.value"
							@click="selectedCategory = category.value"
							:class="[
								'category-btn',
								{ active: selectedCategory === category.value },
							]"
						>
							{{ category.label }}
						</button>
					</div>
				</div>

				<!-- Template List -->
				<div class="modal-body">
					<div v-if="isLoading" class="loading-state">
						<div class="spinner"></div>
						<span>Loading prompts...</span>
					</div>

					<div v-else-if="filteredTemplates.length === 0" class="empty-state">
						<svg
							class="empty-icon"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="1.5"
								d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
							/>
						</svg>
						<p class="empty-title">No prompts available</p>
						<p class="empty-description">
							{{
								searchQuery || selectedCategory !== "all"
									? "Try adjusting your search or filters"
									: "Prompts will appear here once configured"
							}}
						</p>
					</div>

					<div v-else class="template-grid">
						<div
							v-for="template in filteredTemplates"
							:key="template.name"
							class="template-card"
						>
							<div class="template-header">
								<span class="template-icon">{{
									getCategoryIcon(template.category)
								}}</span>
								<div class="template-info">
									<h3 class="template-title">{{ template.title }}</h3>
									<span class="template-category">{{
										formatCategory(template.category)
									}}</span>
								</div>
								<button
									@click="togglePin(template)"
									:class="['pin-btn', { pinned: isPinned(template.name) }]"
									:title="
										isPinned(template.name)
											? 'Unpin prompt'
											: 'Pin to quick prompts'
									"
									:aria-label="
										isPinned(template.name) ? 'Unpin prompt' : 'Pin prompt'
									"
								>
									<svg
										v-if="isPinned(template.name)"
										class="w-4 h-4"
										fill="currentColor"
										viewBox="0 0 20 20"
									>
										<path
											d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
										/>
									</svg>
									<svg
										v-else
										class="w-4 h-4"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
										/>
									</svg>
								</button>
							</div>
							<p class="template-description">{{ template.description }}</p>
							<div class="template-footer">
								<span v-if="hasArguments(template)" class="args-badge">
									<svg
										class="w-3 h-3"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
										/>
									</svg>
									Customizable
								</span>
								<button @click="$emit('use-template', template)" class="use-btn">
									Use
								</button>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useTemplateStore } from "@/stores/templateStore";
import { storeToRefs } from "pinia";

const props = defineProps({
	isOpen: {
		type: Boolean,
		default: false,
	},
});

const emit = defineEmits(["close", "use-template"]);

const templateStore = useTemplateStore();
const { templates, categories, isLoading, pinnedNames } = storeToRefs(templateStore);

const searchQuery = ref("");
const selectedCategory = ref("all");

// All categories including "All"
const allCategories = computed(() => {
	const cats = [{ value: "all", label: "All" }];
	categories.value.forEach((cat) => {
		cats.push({
			value: cat,
			label: formatCategory(cat),
		});
	});
	return cats;
});

// Filter templates based on search and category
const filteredTemplates = computed(() => {
	let result = templates.value;

	if (selectedCategory.value !== "all") {
		result = result.filter((t) => t.category === selectedCategory.value);
	}

	if (searchQuery.value.trim()) {
		const query = searchQuery.value.toLowerCase();
		result = result.filter(
			(t) =>
				t.title.toLowerCase().includes(query) ||
				t.description.toLowerCase().includes(query)
		);
	}

	return result;
});

const categoryIcons = {
	"data-quality": "🔍",
	documentation: "📄",
	"sales-crm": "📊",
	"hr-payroll": "👥",
	purchasing: "📦",
	manufacturing: "🏭",
};

function getCategoryIcon(category) {
	return categoryIcons[category] || "📋";
}

function formatCategory(category) {
	if (!category) return "General";
	return category
		.split("-")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ");
}

function isPinned(templateName) {
	return templateStore.isPinned(templateName);
}

function togglePin(template) {
	templateStore.togglePin(template.name);
}

function hasArguments(template) {
	return template.arguments && template.arguments.length > 0;
}

// Load templates when modal opens
watch(
	() => props.isOpen,
	(newVal) => {
		if (newVal && templates.value.length === 0) {
			templateStore.loadTemplates();
		}
	}
);

// Reset filters when modal closes
watch(
	() => props.isOpen,
	(newVal) => {
		if (!newVal) {
			searchQuery.value = "";
			selectedCategory.value = "all";
		}
	}
);
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background-color: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1000;
	padding: 1rem;
}

.modal-container {
	background-color: var(--ql-bg);
	border-radius: 0.75rem;
	box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
	width: 100%;
	max-width: 48rem;
	max-height: 85vh;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}

.modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1rem 1.5rem;
	border-bottom: 1px solid var(--ql-border);
}

.modal-title {
	font-size: 1.25rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.close-btn {
	padding: 0.5rem;
	border-radius: 0.375rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	cursor: pointer;
	transition: all 0.15s ease;
}

.close-btn:hover {
	background-color: var(--ql-surface);
	color: var(--ql-text);
}

.close-btn svg {
	width: 1.25rem;
	height: 1.25rem;
}

.modal-filters {
	padding: 1rem 1.5rem;
	border-bottom: 1px solid var(--ql-border);
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

.search-wrapper {
	position: relative;
}

.search-icon {
	position: absolute;
	left: 0.75rem;
	top: 50%;
	transform: translateY(-50%);
	width: 1.25rem;
	height: 1.25rem;
	color: var(--ql-text-muted);
}

.search-input {
	width: 100%;
	padding: 0.625rem 0.75rem 0.625rem 2.5rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	background-color: var(--ql-surface);
	color: var(--ql-text);
	font-size: 0.875rem;
	transition: border-color 0.15s ease;
}

.search-input:focus {
	outline: none;
	border-color: var(--ql-accent);
}

.search-input::placeholder {
	color: var(--ql-text-muted);
}

.category-filter {
	display: flex;
	flex-wrap: wrap;
	gap: 0.5rem;
}

.category-btn {
	padding: 0.375rem 0.75rem;
	border: 1px solid var(--ql-border);
	border-radius: 9999px;
	background-color: transparent;
	color: var(--ql-text-muted);
	font-size: 0.8125rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.category-btn:hover {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}

.category-btn.active {
	background-color: var(--ql-accent);
	border-color: var(--ql-accent);
	color: white;
}

.modal-body {
	flex: 1;
	overflow-y: auto;
	padding: 1.5rem;
}

.loading-state,
.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 3rem 1rem;
	text-align: center;
}

.spinner {
	width: 2rem;
	height: 2rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
	margin-bottom: 1rem;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.empty-icon {
	width: 4rem;
	height: 4rem;
	color: var(--ql-text-muted);
	margin-bottom: 1rem;
}

.empty-title {
	font-size: 1rem;
	font-weight: 500;
	color: var(--ql-text);
	margin: 0 0 0.5rem 0;
}

.empty-description {
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	margin: 0;
}

.template-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
	gap: 1rem;
}

.template-card {
	background-color: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 1rem;
	display: flex;
	flex-direction: column;
	transition: border-color 0.15s ease;
}

.template-card:hover {
	border-color: var(--ql-accent);
}

.template-header {
	display: flex;
	align-items: flex-start;
	gap: 0.75rem;
	margin-bottom: 0.75rem;
}

.template-icon {
	font-size: 1.5rem;
	line-height: 1;
	flex-shrink: 0;
}

.template-info {
	flex: 1;
	min-width: 0;
}

.template-title {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.25rem 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.template-category {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.pin-btn {
	padding: 0.375rem;
	border: none;
	border-radius: 0.375rem;
	background: transparent;
	color: var(--ql-text-muted);
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.pin-btn:hover {
	background-color: var(--ql-bg);
	color: var(--ql-accent);
}

.pin-btn.pinned {
	color: #f59e0b;
}

.pin-btn svg {
	width: 1rem;
	height: 1rem;
}

.template-description {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
	margin: 0 0 1rem 0;
	flex: 1;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.template-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
}

.args-badge {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	padding: 0.25rem 0.5rem;
	background-color: var(--ql-bg);
	border-radius: 0.25rem;
}

.args-badge svg {
	width: 0.75rem;
	height: 0.75rem;
}

.use-btn {
	padding: 0.5rem 1rem;
	background-color: var(--ql-accent);
	color: white;
	border: none;
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	font-weight: 500;
	cursor: pointer;
	transition: background-color 0.15s ease;
	margin-left: auto;
}

.use-btn:hover {
	background-color: var(--ql-accent-hover);
}

/* Responsive */
@media (max-width: 640px) {
	.modal-container {
		max-height: 90vh;
	}

	.template-grid {
		grid-template-columns: 1fr;
	}

	.category-filter {
		overflow-x: auto;
		flex-wrap: nowrap;
		padding-bottom: 0.5rem;
	}

	.category-btn {
		flex-shrink: 0;
	}
}
</style>
