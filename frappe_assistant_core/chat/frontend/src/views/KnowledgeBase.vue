<template>
	<div class="app-layout">
		<NavigationSidebar
			:collapsed="sidebarCollapsed"
			@open-settings="router.push('/settings')"
			@toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
		/>

		<main class="main-content">
			<!-- Top Bar -->
			<KnowledgeTopBar
				:memory-enabled="memoryEnabled"
				:can-upload="knowledgeIncluded"
				:storage="storage"
				@toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
				@upload="triggerUpload"
			/>

			<!-- Knowledge Base Content -->
			<div
				class="kb-content"
				@dragover.prevent="onDragOver"
				@dragleave.prevent="onDragLeave"
				@drop.prevent="onDrop($event)"
			>
				<!-- Not Available State -->
				<KnowledgeStates v-if="!memoryEnabled" status="unavailable" />

				<!-- Skeleton Loading State -->
				<KnowledgeSkeleton v-else-if="loading" />

				<!-- Error State -->
				<KnowledgeStates
					v-else-if="loadError"
					status="error"
					:error="loadError"
					@retry="loadDocuments"
				/>

				<!-- Documents Content -->
				<template v-else>
					<!-- Drag Overlay -->
					<KnowledgeStates v-if="isDragging" status="dragging" />

					<ListPageShell :grid="false">
						<template #header>
							<ListHeaderBand title="Knowledge Base" :stat="storageStat">
								<template #actions>
									<input
										v-if="hasDocuments"
										v-model="searchQuery"
										class="ql-search"
										type="search"
										placeholder="Search…"
									/>
									<button
										v-if="knowledgeIncluded"
										class="ql-primary-action"
										@click="triggerUpload"
									>
										+ Upload
									</button>
								</template>
							</ListHeaderBand>
						</template>

						<!-- Toolbar row: shared-knowledge banner, upload error,
						     filter/search/view controls — full-width, above the grid. -->
						<template #toolbar>
							<SharedKnowledge :is-admin="isAdmin" />

							<div v-if="uploadError" class="upload-error-banner">
								<svg
									class="w-4 h-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
									/>
								</svg>
								<span>{{ uploadError }}</span>
								<button
									class="dismiss-btn"
									@click="uploadError = null"
									aria-label="Dismiss error"
								>
									<svg
										class="w-4 h-4"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M6 18L18 6M6 6l12 12"
										/>
									</svg>
								</button>
							</div>

							<KnowledgeToolbar
								v-if="hasDocuments"
								ref="toolbarRef"
								v-model:searchQuery="searchQuery"
								v-model:activeFilter="activeFilter"
								v-model:viewMode="viewMode"
							/>
						</template>

						<!-- Default slot (grid=false): KnowledgeDocumentGrid owns its
						     own grid; the add tile is passed in as its trailing cell. -->
						<EmptyState
							v-if="!hasDocuments"
							title="Your knowledge base is empty"
							description="Upload documents and FACO will use them to give you smarter, more contextual answers."
							:cta="knowledgeIncluded ? 'Upload your first document' : ''"
							@cta="triggerUpload"
						>
							<template #footnote>
								<p class="kb-empty-foot">
									Supports PDF, Markdown, and Text up to 10 MB — or drag and drop
									anywhere on this page.
								</p>
							</template>
						</EmptyState>

						<div
							v-else-if="filteredDocuments.length === 0 && uploads.length === 0"
							class="no-results"
						>
							<p>No documents match your search.</p>
							<button
								class="no-results-clear"
								@click="
									searchQuery = '';
									activeFilter = 'all';
								"
							>
								Clear filters
							</button>
						</div>

						<KnowledgeDocumentGrid
							v-else
							:documents="filteredDocuments"
							:uploads="uploads"
							:view-mode="viewMode"
							:is-admin="isAdmin"
							@preview="openPreview"
							@delete="confirmDelete"
							@manage-access="openAccessModal"
						>
							<AddSlotCard
								v-if="knowledgeIncluded"
								label="Add document"
								@click="triggerUpload"
							/>
						</KnowledgeDocumentGrid>
					</ListPageShell>
				</template>

				<!-- Hidden file input -->
				<input
					ref="fileInput"
					type="file"
					class="hidden-input"
					multiple
					accept=".pdf,.md,.txt,.markdown,.text"
					@change="handleFileSelect"
				/>
			</div>
		</main>

		<UploadConfirmModal
			:files="pendingFiles"
			@confirm="handleUploadConfirm"
			@cancel="cancelPending"
		/>

		<DeleteConfirmDialog
			:doc="deleteTarget"
			:deleting="deleting"
			@cancel="deleteTarget = null"
			@confirm="handleDelete"
		/>

		<DocumentAccessModal
			:doc="accessTarget"
			@close="accessTarget = null"
			@updated="onAccessUpdated"
		/>

		<DocumentPreviewPanel
			:doc="previewDoc"
			@close="previewDoc = null"
			@manage-access="openAccessModal"
			@view-chunks="(doc) => (chunkBrowserDoc = doc)"
		/>

		<ChunkBrowserPanel :doc="chunkBrowserDoc" @close="chunkBrowserDoc = null" />
	</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useUserStore } from "@/stores/userStore";
import { useDocumentUpload } from "@/composables/useDocumentUpload";
import NavigationSidebar from "@/components/layout/NavigationSidebar.vue";
import KnowledgeTopBar from "@/components/knowledge/KnowledgeTopBar.vue";
import SharedKnowledge from "@/components/knowledge/SharedKnowledge.vue";
import DocumentPreviewPanel from "@/components/knowledge/DocumentPreviewPanel.vue";
import ChunkBrowserPanel from "@/components/knowledge/ChunkBrowserPanel.vue";
import DeleteConfirmDialog from "@/components/knowledge/DeleteConfirmDialog.vue";
import UploadConfirmModal from "@/components/knowledge/UploadConfirmModal.vue";
import DocumentAccessModal from "@/components/knowledge/DocumentAccessModal.vue";
import KnowledgeSkeleton from "@/components/knowledge/KnowledgeSkeleton.vue";
import KnowledgeStates from "@/components/knowledge/KnowledgeStates.vue";
import KnowledgeToolbar from "@/components/knowledge/KnowledgeToolbar.vue";
import KnowledgeDocumentGrid from "@/components/knowledge/KnowledgeDocumentGrid.vue";
import ListPageShell from "@/components/common/list/ListPageShell.vue";
import ListHeaderBand from "@/components/common/list/ListHeaderBand.vue";
import AddSlotCard from "@/components/common/list/AddSlotCard.vue";
import EmptyState from "@/components/common/list/EmptyState.vue";
import { api } from "@/api/client";

const router = useRouter();
const userStore = useUserStore();
const { isAdmin, memoryEnabled, quotaInfo } = storeToRefs(userStore);

// Absent means an older server that doesn't say. Only an explicit false hides
// Upload, so a plan that excludes the knowledge base can't offer a button
// whose request then fails.
const knowledgeIncluded = computed(
	() => quotaInfo.value?.features?.knowledge_base !== false
);

const sidebarCollapsed = ref(false);
const loading = ref(true);
const loadError = ref(null);
const documents = ref([]);
const storage = ref(null);
const deleteTarget = ref(null);
const deleting = ref(false);
const previewDoc = ref(null);
const chunkBrowserDoc = ref(null);
const accessTarget = ref(null);
const activeFilter = ref("all");
const searchQuery = ref("");
const viewMode = ref("grid");
const toolbarRef = ref(null);

const filteredDocuments = computed(() => {
	let docs = documents.value;
	if (activeFilter.value === "mine") docs = docs.filter((d) => d.is_owner);
	else if (activeFilter.value !== "all")
		docs = docs.filter((d) => d.visibility === activeFilter.value);
	if (searchQuery.value.trim()) {
		const q = searchQuery.value.toLowerCase();
		docs = docs.filter((d) => d.file_name.toLowerCase().includes(q));
	}
	return docs;
});

const storageStat = computed(() => {
	const n = documents.value.length;
	const docWord = n === 1 ? "document" : "documents";
	// storage_info returns { used_mb, quota_mb, usage_percentage } — quota_mb is the limit
	const used = storage.value ? (storage.value.used_mb ?? 0).toFixed(1) : "0.0";
	const limit = storage.value ? (storage.value.quota_mb ?? 10) : 10;
	return `${n} ${docWord} · ${used} of ${limit} MB used`;
});

const {
	uploads,
	uploadError,
	isDragging,
	fileInput,
	pendingFiles,
	triggerUpload,
	handleFileSelect,
	confirmUpload,
	cancelPending,
	onDragOver,
	onDragLeave,
	onDrop: dropFiles,
} = useDocumentUpload({
	onUploaded: loadDocuments,
	onFilesSelected: () => {},
});

// A plan that excludes the knowledge base has no upload path at all, including
// drag-and-drop, which would otherwise fail after the file was accepted.
function onDrop(event) {
	if (knowledgeIncluded.value) dropFiles(event);
}

let pollInterval = null;

const hasDocuments = computed(() => documents.value.length > 0 || uploads.value.length > 0);

const hasProcessing = computed(() =>
	documents.value.some((d) => ["Pending", "Processing"].includes(d.embedding_status)),
);

async function loadDocuments() {
	try {
		loadError.value = null;
		const result = await api.documents.list();
		if (result) {
			documents.value = result.documents || [];
			storage.value = result.storage || null;
		}
	} catch (e) {
		loadError.value = e.message || "Failed to load documents";
	} finally {
		loading.value = false;
	}
}

function confirmDelete(doc) {
	deleteTarget.value = doc;
}

async function handleDelete() {
	if (!deleteTarget.value) return;
	deleting.value = true;
	try {
		await api.documents.delete(deleteTarget.value.document_id);
		documents.value = documents.value.filter(
			(d) => d.document_id !== deleteTarget.value.document_id,
		);
		deleteTarget.value = null;
		try {
			const storageResult = await api.documents.getStorageInfo();
			if (storageResult) storage.value = storageResult;
		} catch {}
	} catch (e) {
		uploadError.value = e.message || "Failed to delete document";
	} finally {
		deleting.value = false;
	}
}

function handleUploadConfirm({ visibility, sharedWith }) {
	confirmUpload(visibility, sharedWith);
}

function openPreview(doc) {
	previewDoc.value = doc;
}

function openAccessModal(doc) {
	accessTarget.value = doc;
}

function onAccessUpdated() {
	accessTarget.value = null;
	loadDocuments();
}

function handleKeydown(e) {
	if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
		const tag = document.activeElement?.tagName;
		if (tag === "INPUT" || tag === "TEXTAREA" || document.activeElement?.isContentEditable)
			return;
		e.preventDefault();
		toolbarRef.value?.focus();
	}
}

watch(hasProcessing, (val) => {
	if (val && !pollInterval) {
		pollInterval = setInterval(() => loadDocuments(), 5000);
	} else if (!val && pollInterval) {
		clearInterval(pollInterval);
		pollInterval = null;
	}
});

onMounted(async () => {
	document.addEventListener("keydown", handleKeydown);
	if (memoryEnabled.value) {
		await loadDocuments();
	} else {
		loading.value = false;
	}
});

onUnmounted(() => {
	document.removeEventListener("keydown", handleKeydown);
	if (pollInterval) {
		clearInterval(pollInterval);
		pollInterval = null;
	}
});
</script>

<style scoped>
/* Layout */
.app-layout {
	display: flex;
	height: 100%;
	min-height: 0;
	overflow: hidden;
	background-color: var(--ql-bg);
}

.main-content {
	flex: 1;
	display: flex;
	flex-direction: column;
	min-width: 0;
	min-height: 0;
	overflow: hidden;
}

/* KB Content */
.kb-content {
	flex: 1;
	overflow-y: auto;
	padding: 1.5rem;
	position: relative;
	scrollbar-width: thin;
	scrollbar-color: var(--ql-border) transparent;
}

.kb-content::-webkit-scrollbar {
	width: 6px;
}
.kb-content::-webkit-scrollbar-track {
	background: transparent;
}
.kb-content::-webkit-scrollbar-thumb {
	background-color: var(--ql-border);
	border-radius: 3px;
}

/* Upload Error Banner */
.upload-error-banner {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.625rem 1rem;
	background: rgba(180, 69, 58, 0.1);
	border: 1px solid rgba(180, 69, 58, 0.2);
	border-radius: 0.5rem;
	color: var(--ql-danger);
	font-size: 0.875rem;
	margin-bottom: 1rem;
}

.upload-error-banner .dismiss-btn {
	margin-left: auto;
	padding: 0.25rem;
	background: none;
	border: none;
	color: var(--ql-danger);
	cursor: pointer;
	border-radius: 0.25rem;
	transition: background-color 0.15s ease;
}

.upload-error-banner .dismiss-btn:hover {
	background: rgba(180, 69, 58, 0.15);
}

/* No results */
.no-results {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 3rem 1rem;
	gap: 0.5rem;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.no-results-clear {
	padding: 0.375rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-accent);
	background: none;
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.no-results-clear:hover {
	background: var(--ql-accent-soft);
}

/* Documents Section */
.documents-section {
	margin-top: 0;
}

/* Hidden File Input */
.hidden-input {
	display: none;
}

/* Utility */
.w-4 {
	width: 1rem;
	height: 1rem;
}
.w-5 {
	width: 1.25rem;
	height: 1.25rem;
}

/* Responsive */
@media (max-width: 768px) {
	.app-layout {
		position: relative;
	}
	.kb-content {
		padding: 1rem;
	}
}

/* Quiet Ledger list-pattern controls */
.ql-search {
	font-size: 13px;
	color: var(--ql-text);
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	padding: 6px 10px;
	outline: none;
}
.ql-search:focus {
	border-color: var(--ql-accent);
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
.kb-empty-foot {
	font-size: 12px;
	color: var(--ql-text-muted);
	margin-top: 12px;
}
</style>
