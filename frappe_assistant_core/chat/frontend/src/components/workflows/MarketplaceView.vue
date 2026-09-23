<template>
	<div class="marketplace">
		<!-- Creator stats (for tenants with published templates) -->
		<CreatorStatsSection
			v-if="store.creatorStats?.templates_published > 0"
			:stats="store.creatorStats"
		/>

		<!-- Top bar -->
		<MarketplaceFilters
			:search-query="searchQuery"
			:category-filter="categoryFilter"
			:sort-by="sortBy"
			:categories="categories"
			@update:search-query="onSearchInput"
			@update:category-filter="setCategory"
			@update:sort-by="onSortChange"
		/>

		<!-- Featured row -->
		<div
			v-if="featuredTemplates.length > 0 && !searchQuery && !categoryFilter"
			class="featured-section"
		>
			<h3 class="section-title">Featured</h3>
			<div class="featured-scroll">
				<TemplateCard
					v-for="tpl in featuredTemplates"
					:key="'featured-' + (tpl.template_name || tpl.name)"
					:template="tpl"
					:featured="true"
					@select="selectTemplate"
				/>
			</div>
		</div>

		<!-- Loading -->
		<div
			v-if="store.isLoadingTemplates && allTemplates.length === 0"
			class="marketplace-loading"
		>
			<div class="loading-spinner"></div>
			<p>Loading templates...</p>
		</div>

		<!-- Empty -->
		<div v-else-if="allTemplates.length === 0" class="marketplace-empty">
			<svg
				width="40"
				height="40"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				class="empty-icon"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="1.5"
					d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
				/>
			</svg>
			<p v-if="searchQuery || categoryFilter">No templates match your search.</p>
			<p v-else>No templates available yet.</p>
		</div>

		<!-- Template grid -->
		<div v-else class="marketplace-grid-section">
			<h3
				v-if="featuredTemplates.length > 0 && !searchQuery && !categoryFilter"
				class="section-title"
			>
				All Templates
			</h3>
			<div class="marketplace-grid">
				<TemplateCard
					v-for="tpl in allTemplates"
					:key="tpl.template_name || tpl.name"
					:template="tpl"
					@select="selectTemplate"
					@quick-use="quickUseTemplate"
				/>
			</div>

			<!-- Load More -->
			<div v-if="hasMore" class="load-more-wrap">
				<button
					class="load-more-btn"
					:disabled="store.isLoadingTemplates"
					@click="loadMore"
				>
					<span v-if="store.isLoadingTemplates" class="loading-spinner small"></span>
					<span v-else>Load More</span>
				</button>
			</div>
		</div>

		<!-- Template Detail Panel (slide-over) -->
		<TemplateDetailPanel
			:template="detailTemplate"
			:start-in-import-mode="startInImportMode"
			@close="closePanel"
			@created="handleWorkflowCreated"
			@rated="onTemplateRated"
		/>
	</div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { storeToRefs } from "pinia";
import { useWorkflowStore } from "@/stores/workflowStore";
import { logger } from "@/utils/logger";
import MarketplaceFilters from "./marketplace/MarketplaceFilters.vue";
import TemplateCard from "./marketplace/TemplateCard.vue";
import CreatorStatsSection from "./marketplace/CreatorStatsSection.vue";
import TemplateDetailPanel from "./TemplateDetailPanel.vue";

const emit = defineEmits(["workflow-created"]);

const store = useWorkflowStore();
const { templates: allTemplates, templatesTotal, isLoadingTemplates } = storeToRefs(store);

const searchQuery = ref("");
const categoryFilter = ref(null);
const sortBy = ref("");
const currentPage = ref(0);
const featuredTemplates = ref([]);
const detailTemplate = ref(null);
const startInImportMode = ref(false);

const categories = [
	"All",
	"General",
	"Sales",
	"Marketing",
	"Support",
	"Operations",
	"Finance",
	"Procurement",
	"Development",
	"Custom",
];

const hasMore = computed(() => allTemplates.value.length < templatesTotal.value);

let searchTimer = null;

onMounted(async () => {
	await reloadTemplates();
	await loadFeatured();
	store.loadCreatorStats();
});

function getActiveCategory() {
	return categoryFilter.value === "All" ? null : categoryFilter.value;
}

function getActiveSortBy() {
	return sortBy.value || null;
}

function onSearchInput(value) {
	searchQuery.value = value;
	debouncedSearch();
}

function debouncedSearch() {
	clearTimeout(searchTimer);
	searchTimer = setTimeout(() => {
		currentPage.value = 0;
		reloadTemplates();
	}, 300);
}

function setCategory(cat) {
	categoryFilter.value = cat === categoryFilter.value ? null : cat;
	currentPage.value = 0;
	reloadTemplates();
}

function onSortChange(value) {
	sortBy.value = value;
	reloadTemplates();
}

async function reloadTemplates() {
	currentPage.value = 0;
	await store.loadTemplates(
		getActiveCategory(),
		searchQuery.value || null,
		getActiveSortBy(),
		0
	);
}

async function loadMore() {
	currentPage.value++;
	await store.loadTemplates(
		getActiveCategory(),
		searchQuery.value || null,
		getActiveSortBy(),
		currentPage.value,
		{ append: true }
	);
}

async function loadFeatured() {
	try {
		// Use API directly — NOT the store — to avoid overwriting the main templates list
		const { api } = await import("@/api/client");
		const res = await api.workflows.listTemplates(null, null, null, true, null, 0, 6);
		featuredTemplates.value = res.templates || [];
	} catch {
		featuredTemplates.value = [];
	}
}

async function selectTemplate(tpl) {
	try {
		startInImportMode.value = false;
		const full = await store.loadTemplate(tpl.template_name || tpl.name);
		detailTemplate.value = full;
	} catch (err) {
		logger.error("Failed to load template details:", err);
	}
}

async function quickUseTemplate(tpl) {
	try {
		startInImportMode.value = true;
		const full = await store.loadTemplate(tpl.template_name || tpl.name);
		detailTemplate.value = full;
	} catch (err) {
		logger.error("Failed to load template details:", err);
	}
}

function closePanel() {
	detailTemplate.value = null;
	startInImportMode.value = false;
}

function handleWorkflowCreated(name) {
	detailTemplate.value = null;
	startInImportMode.value = false;
	emit("workflow-created", name);
}

function onTemplateRated(result) {
	if (detailTemplate.value && result) {
		detailTemplate.value.average_rating =
			result.average_rating ?? detailTemplate.value.average_rating;
		detailTemplate.value.rating_count =
			result.rating_count ?? detailTemplate.value.rating_count;
	}
}
</script>

<style scoped>
.marketplace {
	display: flex;
	flex-direction: column;
}

/* Featured section */
.featured-section {
	padding: 0 1.5rem;
	margin-bottom: 1.25rem;
}

.section-title {
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.75rem;
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.featured-scroll {
	display: flex;
	gap: 0.75rem;
	overflow-x: auto;
	padding-bottom: 0.5rem;
	scrollbar-width: thin;
	scrollbar-color: var(--ql-border) transparent;
}

.featured-scroll::-webkit-scrollbar {
	height: 4px;
}

.featured-scroll::-webkit-scrollbar-track {
	background: transparent;
}

.featured-scroll::-webkit-scrollbar-thumb {
	background: var(--ql-border);
	border-radius: 2px;
}

/* Main grid */
.marketplace-grid-section {
	padding: 0 1.5rem 1.5rem;
}

.marketplace-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
	gap: 0.875rem;
}

/* Load more */
.load-more-wrap {
	display: flex;
	justify-content: center;
	padding: 1.25rem 0 0;
}

.load-more-btn {
	padding: 0.5rem 1.5rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
}

.load-more-btn:hover:not(:disabled) {
	border-color: var(--ql-accent);
	color: var(--ql-accent);
}

.load-more-btn:disabled {
	opacity: 0.6;
	cursor: default;
}

/* Loading / empty */
.marketplace-loading,
.marketplace-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 4rem 1rem;
	color: var(--ql-text-muted);
	font-size: 0.8125rem;
}

.empty-icon {
	margin-bottom: 1rem;
	opacity: 0.4;
}

.loading-spinner {
	width: 1.5rem;
	height: 1.5rem;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
	margin-bottom: 0.75rem;
}

.loading-spinner.small {
	width: 1rem;
	height: 1rem;
	margin-bottom: 0;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

@media (max-width: 640px) {
	.marketplace-grid {
		grid-template-columns: 1fr;
	}
}
</style>
