<template>
	<Teleport to="body">
		<div v-if="modelValue" class="modal-overlay" @click.self="close">
			<div class="modal-content">
				<!-- Header -->
				<div class="modal-header">
					<h2 class="modal-title">Upload Template</h2>
					<button @click="close" class="close-btn" title="Close" aria-label="Close">
						<svg
							width="18"
							height="18"
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

				<!-- Body -->
				<div class="modal-body">
					<!-- Drop zone -->
					<div
						class="drop-zone"
						:class="{ 'drag-over': isDragging, 'has-file': selectedFile }"
						@click="triggerFileInput"
						@dragenter.prevent="isDragging = true"
						@dragover.prevent="isDragging = true"
						@dragleave.prevent="isDragging = false"
						@drop.prevent="onDrop"
					>
						<input
							ref="fileInput"
							type="file"
							accept=".json"
							class="file-input-hidden"
							@change="onFileSelected"
						/>

						<template v-if="!selectedFile">
							<svg
								class="drop-icon"
								width="32"
								height="32"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="1.5"
									d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
								/>
							</svg>
							<p class="drop-text">Drop a .json file or click to browse</p>
							<p class="drop-hint">Workflow template files only</p>
						</template>

						<template v-else>
							<div class="file-selected">
								<svg
									width="20"
									height="20"
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
								<span class="file-name">{{ selectedFile.name }}</span>
								<button
									class="remove-file"
									@click.stop="clearFile"
									title="Remove file"
									aria-label="Remove file"
								>
									<svg
										width="14"
										height="14"
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
						</template>
					</div>

					<!-- Parse error -->
					<div v-if="parseError" class="error-message">
						<svg
							width="14"
							height="14"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
							/>
						</svg>
						{{ parseError }}
					</div>

					<!-- Preview -->
					<div v-if="previewData" class="preview-section">
						<h3 class="section-label">Template Preview</h3>
						<div class="preview-grid">
							<div class="preview-item">
								<span class="preview-label">Name</span>
								<span class="preview-value">{{ previewData.template_name }}</span>
							</div>
							<div class="preview-item">
								<span class="preview-label">Category</span>
								<span class="preview-value">{{
									previewData.category || "General"
								}}</span>
							</div>
							<div v-if="previewData.description" class="preview-item full-width">
								<span class="preview-label">Description</span>
								<span class="preview-value">{{ previewData.description }}</span>
							</div>
							<div v-if="nodeCount > 0" class="preview-item">
								<span class="preview-label">Nodes</span>
								<span class="preview-value">{{ nodeCount }}</span>
							</div>
						</div>
					</div>

					<!-- Options -->
					<div v-if="previewData" class="options-section">
						<label class="checkbox-label">
							<input type="checkbox" v-model="isPublic" class="checkbox-input" />
							<span class="checkbox-text">Make available to all tenants</span>
						</label>
					</div>
				</div>

				<!-- Footer -->
				<div class="modal-footer">
					<button class="btn-secondary" @click="close">Cancel</button>
					<button
						class="btn-primary"
						:disabled="!previewData || isUploading"
						@click="upload"
					>
						<span v-if="isUploading" class="loading-spinner small"></span>
						<span v-else>Upload</span>
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, computed } from "vue";
import { useWorkflowStore } from "@/stores/workflowStore";
import { logger } from "@/utils/logger";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "uploaded"]);

const store = useWorkflowStore();

const fileInput = ref(null);
const selectedFile = ref(null);
const previewData = ref(null);
const parseError = ref(null);
const isPublic = ref(false);
const isUploading = ref(false);
const isDragging = ref(false);

const nodeCount = computed(() => {
	if (!previewData.value?.graph_json) return 0;
	const graph =
		typeof previewData.value.graph_json === "string"
			? JSON.parse(previewData.value.graph_json)
			: previewData.value.graph_json;
	return graph?.nodes?.length || 0;
});

function triggerFileInput() {
	fileInput.value?.click();
}

function onFileSelected(event) {
	const file = event.target.files?.[0];
	if (file) processFile(file);
}

function onDrop(event) {
	isDragging.value = false;
	const file = event.dataTransfer?.files?.[0];
	if (file) processFile(file);
}

function processFile(file) {
	if (!file.name.endsWith(".json")) {
		parseError.value = "Only .json files are accepted";
		selectedFile.value = null;
		previewData.value = null;
		return;
	}

	selectedFile.value = file;
	parseError.value = null;
	previewData.value = null;

	const reader = new FileReader();
	reader.onload = (e) => {
		try {
			const data = JSON.parse(e.target.result);
			if (!data.graph_json && !data.template_name) {
				parseError.value = "Missing required fields (graph_json or template_name)";
				return;
			}
			previewData.value = data;
			parseError.value = null;
		} catch {
			parseError.value = "Invalid JSON file";
			previewData.value = null;
		}
	};
	reader.readAsText(file);
}

function clearFile() {
	selectedFile.value = null;
	previewData.value = null;
	parseError.value = null;
	if (fileInput.value) fileInput.value.value = "";
}

async function upload() {
	if (!selectedFile.value || !previewData.value || isUploading.value) return;
	isUploading.value = true;
	try {
		const result = await store.uploadTemplate(selectedFile.value, isPublic.value);
		emit("uploaded", result);
		emit("update:modelValue", false);
		clearFile();
	} catch (err) {
		logger.error("Failed to upload template:", err);
		parseError.value = err.message || "Upload failed";
	} finally {
		isUploading.value = false;
	}
}

function close() {
	emit("update:modelValue", false);
	clearFile();
	isPublic.value = false;
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1050;
	padding: 1rem;
}

.modal-content {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	width: 100%;
	max-width: 28rem;
	max-height: 85vh;
	display: flex;
	flex-direction: column;
	box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 1rem 1.25rem;
	border-bottom: 1px solid var(--ql-border);
	flex-shrink: 0;
}

.modal-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.close-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.close-btn:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

.modal-body {
	flex: 1;
	overflow-y: auto;
	padding: 1.25rem;
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

/* Drop zone */
.drop-zone {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 2rem 1.5rem;
	border: 2px dashed var(--ql-border);
	border-radius: 0.625rem;
	cursor: pointer;
	transition: all 0.15s ease;
	text-align: center;
}

.drop-zone:hover,
.drop-zone.drag-over {
	border-color: var(--ql-accent);
	background: var(--ql-accent-soft);
}

.drop-zone.has-file {
	border-style: solid;
	padding: 1rem 1.25rem;
}

.file-input-hidden {
	display: none;
}

.drop-icon {
	color: var(--ql-text-muted);
	margin-bottom: 0.75rem;
	opacity: 0.6;
}

.drop-text {
	font-size: 0.8125rem;
	color: var(--ql-text);
	margin: 0 0 0.25rem;
	font-weight: 500;
}

.drop-hint {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	margin: 0;
}

.file-selected {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	width: 100%;
}

.file-selected svg {
	color: var(--ql-accent);
	flex-shrink: 0;
}

.file-name {
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	text-align: left;
}

.remove-file {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 24px;
	height: 24px;
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.remove-file:hover {
	color: var(--ql-danger);
	background: rgba(239, 68, 68, 0.1);
}

/* Error */
.error-message {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.625rem 0.75rem;
	font-size: 0.75rem;
	color: var(--ql-danger);
	background: rgba(239, 68, 68, 0.08);
	border: 1px solid rgba(239, 68, 68, 0.2);
	border-radius: 0.5rem;
}

.error-message svg {
	flex-shrink: 0;
}

/* Preview */
.preview-section {
	display: flex;
	flex-direction: column;
	gap: 0.625rem;
}

.section-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	margin: 0;
}

.preview-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 0.5rem;
}

.preview-item {
	display: flex;
	flex-direction: column;
	gap: 0.125rem;
	padding: 0.5rem 0.625rem;
	background: var(--ql-bg);
	border-radius: 0.375rem;
}

.preview-item.full-width {
	grid-column: 1 / -1;
}

.preview-label {
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.03em;
}

.preview-value {
	font-size: 0.8125rem;
	color: var(--ql-text);
	line-height: 1.4;
}

/* Options */
.options-section {
	padding-top: 0.25rem;
}

.checkbox-label {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	cursor: pointer;
}

.checkbox-input {
	width: 1rem;
	height: 1rem;
	accent-color: var(--ql-accent);
	cursor: pointer;
}

.checkbox-text {
	font-size: 0.8125rem;
	color: var(--ql-text);
}

/* Footer */
.modal-footer {
	display: flex;
	align-items: center;
	justify-content: flex-end;
	gap: 0.625rem;
	padding: 1rem 1.25rem;
	border-top: 1px solid var(--ql-border);
	flex-shrink: 0;
}

/* Buttons */
.btn-primary {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: white;
	background: var(--ql-accent);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
	min-width: 5rem;
	justify-content: center;
}

.btn-primary:hover:not(:disabled) {
	opacity: 0.9;
}

.btn-primary:disabled {
	opacity: 0.5;
	cursor: default;
}

.btn-secondary {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.5rem 1rem;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.btn-secondary:hover {
	border-color: var(--ql-text);
}

/* Spinner */
.loading-spinner {
	width: 1rem;
	height: 1rem;
	border: 2px solid rgba(255, 255, 255, 0.3);
	border-top-color: white;
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

.loading-spinner.small {
	width: 0.875rem;
	height: 0.875rem;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

@media (max-width: 640px) {
	.modal-content {
		max-width: 100%;
	}

	.preview-grid {
		grid-template-columns: 1fr;
	}
}
</style>
