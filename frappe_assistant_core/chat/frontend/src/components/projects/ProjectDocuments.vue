<template>
	<section
		class="project-docs"
		:class="{ dragging }"
		data-test="project-documents"
		@dragover.prevent="dragging = true"
		@dragleave.self="dragging = false"
		@drop.prevent="onDrop"
	>
		<header class="docs-header">
			<h2 class="docs-title">
				{{ __("Documents") }}<span v-if="documents.length" class="count" data-test="docs-count">· {{ documents.length }}</span>
			</h2>
			<button
				v-if="knowledgeIncluded"
				class="upload-btn"
				data-test="docs-upload"
				:disabled="uploading"
				@click="fileInput.click()"
			>
				{{ uploading ? __("Uploading…") : __("Upload") }}
			</button>
			<input
				v-if="knowledgeIncluded"
				ref="fileInput"
				type="file"
				class="hidden-input"
				multiple
				data-test="docs-file-input"
				:accept="ACCEPT_ATTRIBUTE"
				@change="onFileSelect"
			/>
		</header>

		<div v-if="refreshFailed" class="load-error" data-test="docs-refresh-error">
			<span>{{ __("Couldn't refresh.") }}</span>
			<button class="upload-btn" data-test="docs-refresh-retry" @click="retryRefresh">{{ __("Retry") }}</button>
		</div>

		<div v-if="loadFailed" class="load-error" data-test="docs-error">
			<span>{{ __("Couldn't load this project's documents.") }}</span>
			<button class="upload-btn" data-test="docs-retry" @click="loadDocuments">{{ __("Retry") }}</button>
		</div>
		<p v-else-if="!loading && !documents.length" class="empty" data-test="docs-empty">
			{{ __("No documents yet. Upload files the assistant should know for this project.") }}
		</p>
		<ul v-else class="doc-list">
			<ProjectDocumentRow
				v-for="doc in documents"
				:key="doc.document_id"
				:doc="doc"
				:menu-open="menuDocId === doc.document_id"
				@toggle-menu="toggleMenu(doc.document_id)"
				@close-menu="menuDocId = null"
				@delete="askDelete(doc)"
			/>
		</ul>

		<ConfirmModal
			:open="!!deleteTarget"
			:title="__('Delete document')"
			:message="__('Delete this document? The assistant will no longer use it in this project.')"
			:confirm-label="__('Delete')"
			:cancel-label="__('Cancel')"
			:processing="deleting"
			destructive
			@confirm="removeDocument"
			@cancel="deleteTarget = null"
		/>
	</section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import ConfirmModal from "@/components/common/ConfirmModal.vue";
import ProjectDocumentRow from "@/components/projects/ProjectDocumentRow.vue";
import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import { useUserStore } from "@/stores/userStore";
import { ACCEPT_ATTRIBUTE, validateKnowledgeFile } from "@/utils/knowledgeUpload";
import { __ } from "@/utils/i18n";

const POLL_INTERVAL_MS = 5000;
const PROCESSING_STATES = ["Pending", "Processing"];

const props = defineProps({
	projectId: { type: String, required: true },
});

const { showError, showToast } = useToast();

// Same rule as KnowledgeBase.vue: absent means an older server, only an explicit false hides Upload.
const { quotaInfo } = storeToRefs(useUserStore());
const knowledgeIncluded = computed(() => quotaInfo.value?.features?.knowledge_base !== false);

const documents = ref([]);
const loading = ref(true);
const loadFailed = ref(false);
const refreshFailed = ref(false);
const uploading = ref(false);
const dragging = ref(false);
const fileInput = ref(null);
const menuDocId = ref(null);
const deleteTarget = ref(null);
const deleting = ref(false);

const hasProcessing = computed(() =>
	documents.value.some((d) => PROCESSING_STATES.includes(d.embedding_status))
);

let pollTimer = null;
let failures = 0;
// Bumped whenever this block changes the list itself, so a load that started earlier is dropped.
let mutations = 0;
let unmounted = false;

function notifyFailure(err) {
	showError(err?.message || __("Something went wrong"));
}

function stopPolling() {
	if (pollTimer) clearTimeout(pollTimer);
	pollTimer = null;
}

// A chain of timeouts, not an interval, so a slow load can never overlap the next tick. A failed
// load ends the chain; the next successful load (retry, upload, delete) restarts it.
function schedulePoll() {
	stopPolling();
	if (unmounted || failures > 0 || !hasProcessing.value) return;
	pollTimer = setTimeout(loadDocuments, POLL_INTERVAL_MS);
}

async function loadDocuments() {
	const projectId = props.projectId;
	const epoch = mutations;
	try {
		const result = await api.documents.list({ project: projectId });
		if (projectId !== props.projectId) return;
		failures = 0;
		loadFailed.value = false;
		refreshFailed.value = false;
		if (epoch === mutations) documents.value = result?.documents || [];
	} catch (err) {
		if (projectId !== props.projectId) return;
		failures += 1;
		if (failures === 1) notifyFailure(err);
		loadFailed.value = documents.value.length === 0;
		refreshFailed.value = !loadFailed.value;
	} finally {
		if (projectId === props.projectId) {
			loading.value = false;
			schedulePoll();
		}
	}
}

function retryRefresh() {
	loading.value = true;
	loadDocuments();
}

watch(
	() => props.projectId,
	() => {
		stopPolling();
		documents.value = [];
		loading.value = true;
		loadFailed.value = false;
		refreshFailed.value = false;
		failures = 0;
		menuDocId.value = null;
		loadDocuments();
	},
	{ immediate: true }
);

onBeforeUnmount(() => {
	unmounted = true;
	stopPolling();
});

async function uploadFiles(files) {
	uploading.value = true;
	try {
		for (const file of files) {
			const invalid = validateKnowledgeFile(file);
			if (invalid) {
				showError(invalid);
				continue;
			}
			try {
				await api.documents.upload(file, { project: props.projectId });
				mutations += 1;
			} catch (err) {
				notifyFailure(err);
			}
		}
		await loadDocuments();
	} finally {
		uploading.value = false;
	}
}

function onFileSelect(event) {
	const files = Array.from(event.target.files || []);
	event.target.value = "";
	if (files.length) uploadFiles(files);
}

function onDrop(event) {
	dragging.value = false;
	const files = Array.from(event.dataTransfer?.files || []);
	if (!files.length || !knowledgeIncluded.value) return;
	if (uploading.value) {
		showToast(__("Wait for the current upload to finish"));
		return;
	}
	uploadFiles(files);
}

function toggleMenu(documentId) {
	menuDocId.value = menuDocId.value === documentId ? null : documentId;
}

function askDelete(doc) {
	menuDocId.value = null;
	deleteTarget.value = doc;
}

async function removeDocument() {
	const target = deleteTarget.value;
	deleting.value = true;
	try {
		await api.documents.delete(target.document_id);
		mutations += 1;
		documents.value = documents.value.filter((d) => d.document_id !== target.document_id);
		deleteTarget.value = null;
		failures = 0;
		schedulePoll();
	} catch (err) {
		notifyFailure(err);
	} finally {
		deleting.value = false;
	}
}

// Capture phase, so the check runs before any handler elsewhere on the page stops the click.
function onDocumentClick(event) {
	if (!event.target.closest?.(".doc-menu-root")) menuDocId.value = null;
}

function onDocumentKey(event) {
	if (event.key === "Escape") menuDocId.value = null;
}

function detachListeners() {
	document.removeEventListener("click", onDocumentClick, true);
	document.removeEventListener("keydown", onDocumentKey);
}

watch(menuDocId, (id) => {
	detachListeners();
	if (id) {
		document.addEventListener("click", onDocumentClick, true);
		document.addEventListener("keydown", onDocumentKey);
	}
});
onBeforeUnmount(detachListeners);
</script>

<style scoped>
.project-docs {
	display: flex;
	flex-direction: column;
	gap: 0.625rem;
	padding: 0.875rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	background: var(--ql-surface);
}

.project-docs.dragging {
	border: 1px dashed var(--ql-accent);
}

.docs-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
}

.docs-title {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.05em;
}

.hidden-input {
	display: none;
}

.upload-btn {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.375rem 0.75rem;
	cursor: pointer;
}

.upload-btn:disabled {
	opacity: 0.6;
	cursor: default;
}

.empty {
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.doc-list {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	max-height: 20rem;
	overflow-y: auto;
}

.count {
	margin-left: 0.375rem;
	text-transform: none;
}

.load-error {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
	font-size: 0.875rem;
	color: var(--ql-danger);
}
</style>
