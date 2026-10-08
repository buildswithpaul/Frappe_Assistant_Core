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
						<MyAgentsSection
							:workflows="workflows"
							:is-loading="isLoading"
							:error="listError"
							:total="total"
							:status-filter="statusFilter"
							:current-page="currentPage"
							:page-size="pageSize"
							:is-admin="isAdmin"
							@open="openWorkflow"
							@delete="confirmDelete"
							@duplicate="handleDuplicate"
							@create="showCreateModal = true"
							@filter="(s) => workflowStore.loadWorkflows(s, 0)"
							@page="(p) => workflowStore.loadWorkflows(statusFilter, p)"
							@retry="workflowStore.loadWorkflows(statusFilter, currentPage)"
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
import { useToast } from "@/composables/useToast";
import { __ } from "@/utils/i18n";
import { logger } from "@/utils/logger";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";
import WorkflowListTopBar from "@/components/workflows/WorkflowListTopBar.vue";
import MyAgentsSection from "@/components/workflows/list/MyAgentsSection.vue";
import BlankWorkflowModal from "@/components/workflows/BlankWorkflowModal.vue";
import MarketplaceView from "@/components/workflows/MarketplaceView.vue";
import UploadTemplateModal from "@/components/workflows/UploadTemplateModal.vue";
import WorkflowDeleteModal from "@/components/workflows/WorkflowDeleteModal.vue";

const router = useRouter();
const userStore = useUserStore();
const workflowStore = useWorkflowStore();
const { showError, showSuccess } = useToast();

const { workflowsEnabled } = storeToRefs(userStore);
const isAdmin = computed(() => userStore.isAdmin);
const userPublishingEnabled = computed(() => userStore.userPublishingEnabled);
const { workflows, isLoading, listError, total, statusFilter, currentPage, pageSize } =
	storeToRefs(workflowStore);

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

onMounted(() => {
	if (workflowsEnabled.value) {
		workflowStore.loadWorkflows();
	}
});

async function handleDuplicate(wf) {
	if (isDuplicating.value) return;
	isDuplicating.value = true;
	try {
		await workflowStore.duplicateWorkflow(wf.name);
		showSuccess(__("Agent duplicated"));
	} catch (err) {
		logger.error("Failed to duplicate workflow:", err);
		showError(__("Could not duplicate the agent: {0}", [err?.message || err]));
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
		showError(__("Could not delete the agent: {0}", [err?.message || err]));
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

/* States */
.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 4rem 2rem;
	text-align: center;
	color: var(--ql-text-muted);
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

@media (max-width: 640px) {
	.page-content {
		padding: 1rem;
	}
}
</style>
