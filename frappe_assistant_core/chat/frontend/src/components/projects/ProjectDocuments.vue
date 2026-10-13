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
			<h2 class="docs-title">{{ __("Documents") }}</h2>
			<button class="upload-btn" data-test="docs-upload" :disabled="uploading" @click="fileInput.click()">
				{{ uploading ? __("Uploading…") : __("Upload") }}
			</button>
			<input
				ref="fileInput"
				type="file"
				class="hidden-input"
				multiple
				data-test="docs-file-input"
				:accept="ACCEPT_ATTRIBUTE"
				@change="onFileSelect"
			/>
		</header>

		<p v-if="!loading && !documents.length" class="empty" data-test="docs-empty">
			{{ __("No documents yet. Upload files the assistant should know for this project.") }}
		</p>
		<ul v-else class="doc-list">
			<li v-for="doc in documents" :key="doc.document_id" class="doc-row" data-test="doc-row">
				<span class="doc-name" :title="doc.file_name">{{ doc.file_name }}</span>
				<span class="doc-size">{{ formatFileSize(doc.file_size || 0) }}</span>
				<span class="pill" :class="statusOf(doc).cls" data-test="doc-status">
					{{ statusOf(doc).label }}
				</span>
				<div class="doc-menu-root">
					<button
						class="row-menu"
						data-test="doc-menu"
						aria-haspopup="menu"
						:aria-expanded="menuDocId === doc.document_id"
						:aria-label="__('Document options')"
						@click="toggleMenu(doc.document_id)"
					>
						⋯
					</button>
					<div
						v-if="menuDocId === doc.document_id"
						class="menu"
						role="menu"
						@keydown.esc.stop.prevent="menuDocId = null"
					>
						<a
							class="menu-item"
							role="menuitem"
							data-test="doc-download"
							:href="api.documents.getDownloadUrl(doc.document_id)"
							@click="menuDocId = null"
						>
							{{ __("Download") }}
						</a>
						<button class="menu-item danger" role="menuitem" data-test="doc-delete" @click="askDelete(doc)">
							{{ __("Delete") }}
						</button>
					</div>
				</div>
			</li>
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
import ConfirmModal from "@/components/common/ConfirmModal.vue";
import { api } from "@/api/client";
import { useToast } from "@/composables/useToast";
import { formatFileSize } from "@/composables/useFormatters";
import { ACCEPT_ATTRIBUTE, validateKnowledgeFile } from "@/utils/knowledgeUpload";
import { __ } from "@/utils/i18n";

const POLL_INTERVAL_MS = 5000;
const PROCESSING_STATES = ["Pending", "Processing"];

const props = defineProps({
	projectId: { type: String, required: true },
});

const { showError } = useToast();

const documents = ref([]);
const loading = ref(true);
const uploading = ref(false);
const dragging = ref(false);
const fileInput = ref(null);
const menuDocId = ref(null);
const deleteTarget = ref(null);
const deleting = ref(false);

const hasProcessing = computed(() =>
	documents.value.some((d) => PROCESSING_STATES.includes(d.embedding_status))
);

function statusOf(doc) {
	if (doc.embedding_status === "Completed") return { label: __("Ready"), cls: "ready" };
	if (doc.embedding_status === "Failed") return { label: __("Failed"), cls: "failed" };
	return { label: __("Processing"), cls: "processing" };
}

function notifyFailure(err) {
	showError(err?.message || __("Something went wrong"));
}

async function loadDocuments() {
	const projectId = props.projectId;
	try {
		const result = await api.documents.list({ project: projectId });
		if (projectId === props.projectId) documents.value = result?.documents || [];
	} catch (err) {
		if (projectId === props.projectId) notifyFailure(err);
	} finally {
		if (projectId === props.projectId) loading.value = false;
	}
}

watch(
	() => props.projectId,
	() => {
		documents.value = [];
		loading.value = true;
		menuDocId.value = null;
		loadDocuments();
	},
	{ immediate: true }
);

let pollTimer = null;

function stopPolling() {
	if (pollTimer) clearInterval(pollTimer);
	pollTimer = null;
}

watch(hasProcessing, (processing) => {
	if (processing && !pollTimer) pollTimer = setInterval(loadDocuments, POLL_INTERVAL_MS);
	else if (!processing) stopPolling();
});
onBeforeUnmount(stopPolling);

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
	if (files.length && !uploading.value) uploadFiles(files);
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
		documents.value = documents.value.filter((d) => d.document_id !== target.document_id);
		deleteTarget.value = null;
	} catch (err) {
		notifyFailure(err);
	} finally {
		deleting.value = false;
	}
}

// Capture phase, like ChatRow: the row menu buttons call .stop, so a bubble listener would miss them.
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
}

.doc-row {
	display: flex;
	align-items: center;
	gap: 0.625rem;
	padding: 0.375rem 0;
	font-size: 0.875rem;
	color: var(--ql-text);
}

.doc-name {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.doc-size {
	flex-shrink: 0;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.pill {
	flex-shrink: 0;
	font-size: 0.6875rem;
	font-weight: 600;
	padding: 0.125rem 0.5rem;
	border-radius: 999px;
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}

.pill.ready {
	color: var(--ql-success, #15803d);
}

.pill.failed {
	color: var(--ql-danger);
}

.doc-menu-root {
	position: relative;
	flex-shrink: 0;
}

.row-menu {
	padding: 0.25rem 0.5rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	opacity: 0;
	transition: all 0.15s ease;
}

.doc-row:hover .row-menu,
.row-menu:focus-visible,
.row-menu[aria-expanded="true"] {
	opacity: 1;
}

@media (hover: none) {
	.row-menu {
		opacity: 1;
	}
}

.row-menu:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}

.menu {
	position: absolute;
	right: 0;
	top: 100%;
	z-index: 20;
	min-width: 9rem;
	padding: 0.25rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.menu-item {
	display: block;
	width: 100%;
	box-sizing: border-box;
	text-align: left;
	padding: 0.375rem 0.625rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	text-decoration: none;
}

.menu-item:hover {
	background-color: var(--ql-subtle);
}

.menu-item.danger {
	color: var(--ql-danger);
}
</style>
