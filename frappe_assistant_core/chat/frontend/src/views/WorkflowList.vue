<template>
	<div class="app-layout">
		<NavigationSidebar
			:collapsed="sidebarCollapsed"
			:sessions="[]"
			@toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
			@open-settings="router.push('/settings')"
		/>

		<main class="main-content">
			<!-- Top Bar -->
			<WorkflowListTopBar
				:is-admin="isAdmin"
				:user-publishing-enabled="userPublishingEnabled"
				@toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
				@upload-template="showUploadModal = true"
				@create-workflow="showCreateModal = true"
			/>

			<!-- Content -->
			<div class="page-content">
				<!-- Unavailable state -->
				<div v-if="!workflowsEnabled" class="empty-state">
					<svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="1.5"
							d="M13 10V3L4 14h7v7l9-11h-7z"
						/>
					</svg>
					<h3>Agents Not Available</h3>
					<p>The agents module is not installed on this server.</p>
				</div>

				<template v-else>
					<!-- View Mode Toggle -->
					<div class="view-tabs">
						<button
							class="view-tab"
							:class="{ active: viewMode === 'workflows' }"
							@click="viewMode = 'workflows'"
						>
							My Agents
						</button>
						<button
							class="view-tab"
							:class="{ active: viewMode === 'marketplace' }"
							@click="switchToMarketplace"
						>
							Template Marketplace
						</button>
					</div>

					<!-- Marketplace View -->
					<MarketplaceView
						v-if="viewMode === 'marketplace'"
						@workflow-created="onWorkflowCreated"
					/>

					<!-- Workflows View -->
					<template v-else>
						<!-- Loading -->
						<div v-if="isLoading && workflows.length === 0" class="loading-state">
							<div class="loading-spinner"></div>
							<p>Loading agents…</p>
						</div>

						<!-- Empty State -->
						<EmptyState
							v-else-if="workflows.length === 0"
							title="No agents yet"
							description="Create your first AI agent to automate work intelligently."
							:cta="isAdmin ? 'Create agent' : ''"
							@cta="showCreateModal = true"
						/>

						<!-- Populated -->
						<ListPageShell v-else>
							<template #header>
								<ListHeaderBand title="Agents" :stat="workflowsStat">
									<template #actions>
										<input
											v-model="searchQuery"
											class="list-search"
											type="search"
											placeholder="Search this page…"
											aria-label="Search agents on this page"
										/>
										<div class="filter-tabs">
											<button
												v-for="tab in filterTabs"
												:key="tab.value"
												class="filter-tab"
												:class="{ active: statusFilter === tab.value }"
												@click="handleFilterChange(tab.value)"
											>
												{{ tab.label }}
											</button>
										</div>
										<button
											v-if="isAdmin"
											class="ql-primary-action"
											@click="showCreateModal = true"
										>
											+ New agent
										</button>
									</template>
								</ListHeaderBand>
							</template>

							<WorkflowCard
								v-for="wf in visibleWorkflows"
								:key="wf.name"
								:workflow="wf"
								@click="openWorkflow(wf.name)"
								@delete="confirmDelete(wf)"
								@duplicate="handleDuplicate(wf)"
							/>
							<AddSlotCard
								v-if="isAdmin && !searchQuery"
								label="New agent"
								@click="showCreateModal = true"
							/>
						</ListPageShell>

						<ListPager
							:page="currentPage"
							:page-count="pageCount"
							:disabled="isLoading"
							@change="goToPage"
						/>
					</template>
				</template>
			</div>
		</main>

		<!-- Create Modal -->
		<BlankWorkflowModal v-model="showCreateModal" @created="onWorkflowCreated" />

		<!-- Delete Confirmation Modal -->
		<WorkflowDeleteModal
			v-model="showDeleteModal"
			:workflow="workflowToDelete"
			:is-deleting="isDeleting"
			@confirm="handleDelete"
		/>

		<!-- Upload Template Modal — gated by marketplace user-publishing flag -->
		<UploadTemplateModal
			v-if="userPublishingEnabled"
			v-model="showUploadModal"
			@uploaded="onTemplateUploaded"
		/>
	</div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useWorkflowStore } from "@/stores/workflowStore";
import { logger } from "@/utils/logger";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";
import WorkflowListTopBar from "@/components/workflows/WorkflowListTopBar.vue";
import WorkflowCard from "@/components/workflows/WorkflowCard.vue";
import BlankWorkflowModal from "@/components/workflows/BlankWorkflowModal.vue";
import MarketplaceView from "@/components/workflows/MarketplaceView.vue";
import UploadTemplateModal from "@/components/workflows/UploadTemplateModal.vue";
import WorkflowDeleteModal from "@/components/workflows/WorkflowDeleteModal.vue";
import ListPageShell from "@/components/common/list/ListPageShell.vue";
import ListHeaderBand from "@/components/common/list/ListHeaderBand.vue";
import AddSlotCard from "@/components/common/list/AddSlotCard.vue";
import EmptyState from "@/components/common/list/EmptyState.vue";
import ListPager from "@/components/common/list/ListPager.vue";

const router = useRouter();
const userStore = useUserStore();
const workflowStore = useWorkflowStore();

const { workflowsEnabled } = storeToRefs(userStore);
const isAdmin = computed(() => userStore.isAdmin);
const userPublishingEnabled = computed(() => userStore.userPublishingEnabled);
const { workflows, isLoading, total, statusFilter, currentPage, pageSize } =
	storeToRefs(workflowStore);

const searchQuery = ref("");

// Search filters the loaded page. The list endpoint has no server-side search,
// so the label says exactly that rather than implying a global result.
const visibleWorkflows = computed(() => {
	const q = searchQuery.value.trim().toLowerCase();
	if (!q) return workflows.value;
	return workflows.value.filter(
		(wf) =>
			(wf.workflow_name || "").toLowerCase().includes(q) ||
			(wf.description || "").toLowerCase().includes(q)
	);
});

const pageCount = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize.value)));

const workflowsStat = computed(() => {
	const shown = visibleWorkflows.value.length;
	if (searchQuery.value.trim()) {
		return `${shown} of ${workflows.value.length} on this page match`;
	}
	return `${shown} agent${shown === 1 ? "" : "s"} · ${total.value ?? shown} total`;
});

const sidebarCollapsed = ref(false);
const viewMode = ref("workflows");

// Create modal
const showCreateModal = ref(false);

// Upload modal
const showUploadModal = ref(false);

// Delete modal
const showDeleteModal = ref(false);
const workflowToDelete = ref(null);
const isDeleting = ref(false);
const isDuplicating = ref(false);

const filterTabs = [
	{ label: "All", value: null },
	{ label: "Draft", value: "Draft" },
	{ label: "Active", value: "Active" },
	{ label: "Paused", value: "Paused" },
];

onMounted(() => {
	if (workflowsEnabled.value) {
		workflowStore.loadWorkflows();
	}
});

function handleFilterChange(status) {
	searchQuery.value = "";
	workflowStore.loadWorkflows(status, 0);
}

function goToPage(page) {
	if (page < 0 || page >= pageCount.value) return;
	searchQuery.value = "";
	workflowStore.loadWorkflows(statusFilter.value, page);
}

async function handleDuplicate(wf) {
	if (isDuplicating.value) return;
	isDuplicating.value = true;
	try {
		await workflowStore.duplicateWorkflow(wf.name);
	} catch (err) {
		logger.error("Failed to duplicate workflow:", err);
	} finally {
		isDuplicating.value = false;
	}
}

function openWorkflow(name) {
	router.push({ name: "agent-builder", params: { id: name } });
}

function onWorkflowCreated(name) {
	if (name) {
		router.push({ name: "agent-builder", params: { id: name } });
	}
}

function confirmDelete(wf) {
	workflowToDelete.value = wf;
	showDeleteModal.value = true;
}

function switchToMarketplace() {
	viewMode.value = "marketplace";
}

function onTemplateUploaded() {
	// If in marketplace view, reload templates
	if (viewMode.value === "marketplace") {
		workflowStore.loadTemplates();
	}
}

async function handleDelete() {
	if (!workflowToDelete.value || isDeleting.value) return;
	isDeleting.value = true;
	try {
		await workflowStore.deleteWorkflow(workflowToDelete.value.name);
		showDeleteModal.value = false;
		workflowToDelete.value = null;
	} catch (err) {
		logger.error("Failed to delete workflow:", err);
	} finally {
		isDeleting.value = false;
	}
}
</script>

<style scoped>
.app-layout {
	display: flex;
	height: 100%;
	min-height: 0;
	overflow: hidden;
	background: var(--ql-bg);
}

.main-content {
	flex: 1;
	display: flex;
	flex-direction: column;
	overflow: hidden;
	min-width: 0;
	min-height: 0;
}

.page-content {
	flex: 1;
	overflow-y: auto;
	padding: 1.5rem;
}

/* View Mode Toggle */
.view-tabs {
	display: flex;
	gap: 0;
	margin-bottom: 1.25rem;
	border-bottom: 1px solid var(--ql-border);
}

.view-tab {
	padding: 0.625rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-bottom: 2px solid transparent;
	cursor: pointer;
	transition: all 0.15s ease;
	margin-bottom: -1px;
}

.view-tab:hover {
	color: var(--ql-text);
}

.view-tab.active {
	color: var(--ql-accent);
	border-bottom-color: var(--ql-accent);
}

/* Search + pager */
.list-search {
	padding: 0.375rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 9999px;
	outline: none;
	min-width: 12rem;
}

.list-search:focus {
	border-color: var(--ql-accent);
}

/* Filter Tabs */
.filter-tabs {
	display: flex;
	gap: 0.375rem;
	flex-wrap: wrap;
}

.filter-tab {
	padding: 0.375rem 0.875rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 9999px;
	cursor: pointer;
	transition: all 0.15s ease;
}

.filter-tab:hover {
	color: var(--ql-text);
	border-color: var(--ql-text);
}

.filter-tab.active {
	color: #fff;
	background: var(--ql-accent);
	border-color: var(--ql-accent);
}

/* States */
.loading-state,
.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 4rem 2rem;
	text-align: center;
	color: var(--ql-text-muted);
}

.loading-spinner {
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
	width: 3rem;
	height: 3rem;
	color: var(--ql-text-muted);
	margin-bottom: 1rem;
	opacity: 0.5;
}

.empty-state h3 {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 0.5rem;
}

.empty-state p {
	font-size: 0.875rem;
	margin: 0;
	max-width: 360px;
}

.ql-primary-action {
	font-size: 13px;
	font-weight: 600;
	color: #fff;
	background: var(--ql-accent);
	border: none;
	border-radius: 8px;
	padding: 6px 12px;
	cursor: pointer;
	transition: background 0.15s ease;
}
.ql-primary-action:hover {
	background: var(--ql-accent-hover);
}

@media (max-width: 640px) {
	.page-content {
		padding: 1rem;
	}
}
</style>
