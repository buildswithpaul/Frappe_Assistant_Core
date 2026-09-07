<template>
	<Teleport to="body">
		<div v-if="modelValue" class="modal-overlay" @click.self="close">
			<div class="modal-content">
				<!-- Header -->
				<div class="modal-header">
					<h2 class="modal-title">Share as Template</h2>
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
					<!-- Template name -->
					<div class="form-group">
						<label class="form-label">Template Name</label>
						<input
							v-model="templateName"
							class="form-input"
							placeholder="Enter a name for this template"
							maxlength="140"
						/>
					</div>

					<!-- Category -->
					<div class="form-group">
						<label class="form-label">Category</label>
						<select v-model="category" class="form-select">
							<option v-for="cat in categories" :key="cat" :value="cat">
								{{ cat }}
							</option>
						</select>
					</div>

					<!-- Short description -->
					<div class="form-group">
						<label class="form-label">
							Short Description
							<span
								class="char-counter"
								:class="{ warn: shortDescription.length > 120 }"
							>
								{{ shortDescription.length }}/140
							</span>
						</label>
						<textarea
							v-model="shortDescription"
							class="form-textarea"
							placeholder="Briefly describe what this template does..."
							rows="3"
							maxlength="140"
						></textarea>
					</div>

					<!-- Public toggle -->
					<div class="form-group">
						<label class="checkbox-label">
							<input type="checkbox" v-model="isPublic" class="checkbox-input" />
							<span class="checkbox-text">Make available to all tenants</span>
						</label>
					</div>

					<!-- Error -->
					<div v-if="shareError" class="error-message">
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
						{{ shareError }}
					</div>
				</div>

				<!-- Footer -->
				<div class="modal-footer">
					<button class="btn-secondary" @click="close">Cancel</button>
					<button
						class="btn-primary"
						:disabled="!templateName.trim() || isSharing"
						@click="share"
					>
						<span v-if="isSharing" class="loading-spinner small"></span>
						<span v-else>Share</span>
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, watch } from "vue";
import { useWorkflowStore } from "@/stores/workflowStore";
import { logger } from "@/utils/logger";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	/** AR Workflow docname (WF-#####). publish_workflow does a get_doc on it. */
	workflowId: { type: String, default: "" },
	workflowDisplayName: { type: String, default: "" },
});

const emit = defineEmits(["update:modelValue", "shared"]);

const store = useWorkflowStore();

const templateName = ref("");
const category = ref("General");
const shortDescription = ref("");
const isPublic = ref(false);
const isSharing = ref(false);
const shareError = ref(null);

const categories = [
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

// Pre-fill template name when modal opens
watch(
	() => props.modelValue,
	(visible) => {
		if (visible) {
			templateName.value = props.workflowDisplayName || "";
			category.value = "General";
			shortDescription.value = "";
			isPublic.value = false;
			shareError.value = null;
		}
	}
);

async function share() {
	if (!templateName.value.trim() || isSharing.value) return;
	isSharing.value = true;
	shareError.value = null;
	try {
		const result = await store.exportWorkflow(
			props.workflowId,
			templateName.value.trim(),
			category.value,
			true
		);
		emit("shared", result);
		emit("update:modelValue", false);
	} catch (err) {
		logger.error("Failed to share as template:", err);
		shareError.value = err.message || "Failed to share template";
	} finally {
		isSharing.value = false;
	}
}

function close() {
	emit("update:modelValue", false);
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
	max-width: 26rem;
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

/* Form groups */
.form-group {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}

.form-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.char-counter {
	font-weight: 400;
	text-transform: none;
	letter-spacing: normal;
	font-size: 0.6875rem;
}

.char-counter.warn {
	color: var(--ql-warning);
}

.form-input,
.form-select,
.form-textarea {
	width: 100%;
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	box-sizing: border-box;
	font-family: inherit;
	transition: border-color 0.15s ease;
}

.form-input:focus,
.form-select:focus,
.form-textarea:focus {
	border-color: var(--ql-accent);
}

.form-select {
	cursor: pointer;
	appearance: none;
	-webkit-appearance: none;
	background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%239ca3af' fill='none' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E");
	background-repeat: no-repeat;
	background-position: right 0.625rem center;
	padding-right: 2rem;
}

.form-textarea {
	resize: vertical;
	min-height: 3.5rem;
	line-height: 1.4;
}

/* Checkbox */
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
	min-width: 4.5rem;
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
}
</style>
