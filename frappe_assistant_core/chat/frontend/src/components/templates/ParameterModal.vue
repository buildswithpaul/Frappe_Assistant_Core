<template>
	<Teleport to="body">
		<div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
			<div class="modal-container">
				<!-- Header -->
				<div class="modal-header">
					<div class="header-info">
						<span class="template-icon">{{
							getCategoryIcon(template?.category)
						}}</span>
						<div>
							<h2 class="modal-title">{{ template?.title }}</h2>
							<p class="modal-subtitle">Fill in the details</p>
						</div>
					</div>
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

				<!-- Description -->
				<div v-if="template?.description" class="modal-description">
					{{ template.description }}
				</div>

				<!-- Form -->
				<form @submit.prevent="handleSubmit" class="modal-body">
					<div class="form-fields">
						<div v-for="arg in templateArguments" :key="arg.name" class="form-field">
							<label :for="arg.name" class="field-label">
								{{ formatLabel(arg.name) }}
								<span v-if="arg.required" class="required-indicator">*</span>
							</label>

							<p v-if="arg.description" class="field-description">
								{{ arg.description }}
							</p>

							<!-- Select for enum types -->
							<select
								v-if="arg.enum && arg.enum.length > 0"
								:id="arg.name"
								v-model="formValues[arg.name]"
								class="field-input field-select"
								:required="arg.required"
							>
								<option value="" disabled>Select an option...</option>
								<option v-for="option in arg.enum" :key="option" :value="option">
									{{ option }}
								</option>
							</select>

							<!-- Textarea for long text -->
							<textarea
								v-else-if="isLongText(arg)"
								:id="arg.name"
								v-model="formValues[arg.name]"
								class="field-input field-textarea"
								:placeholder="
									arg.default ||
									`Enter ${formatLabel(arg.name).toLowerCase()}...`
								"
								:required="arg.required"
								rows="3"
							></textarea>

							<!-- Regular input -->
							<input
								v-else
								:id="arg.name"
								v-model="formValues[arg.name]"
								:type="getInputType(arg)"
								class="field-input"
								:placeholder="
									arg.default ||
									`Enter ${formatLabel(arg.name).toLowerCase()}...`
								"
								:required="arg.required"
							/>
						</div>
					</div>

					<!-- Footer -->
					<div class="modal-footer">
						<button type="button" @click="$emit('close')" class="cancel-btn">
							Cancel
						</button>
						<button type="submit" class="submit-btn" :disabled="isSubmitting">
							<span v-if="isSubmitting" class="spinner-small"></span>
							{{ isSubmitting ? "Preparing..." : "Use" }}
						</button>
					</div>
				</form>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { logger } from "@/utils/logger";

const props = defineProps({
	isOpen: {
		type: Boolean,
		default: false,
	},
	template: {
		type: Object,
		default: null,
	},
});

const emit = defineEmits(["close", "submit"]);

const formValues = ref({});
const isSubmitting = ref(false);

// Get template arguments
const templateArguments = computed(() => {
	if (!props.template?.arguments) return [];
	return props.template.arguments;
});

// Initialize form values when template changes
watch(
	() => props.template,
	(newTemplate) => {
		if (newTemplate?.arguments) {
			const values = {};
			newTemplate.arguments.forEach((arg) => {
				// Use default value if available
				values[arg.name] = arg.default || "";
			});
			formValues.value = values;
		}
	},
	{ immediate: true }
);

// Reset form when modal closes
watch(
	() => props.isOpen,
	(isOpen) => {
		if (!isOpen) {
			isSubmitting.value = false;
		}
	}
);

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

function formatLabel(name) {
	if (!name) return "";
	return name
		.replace(/_/g, " ")
		.replace(/-/g, " ")
		.split(" ")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ");
}

function getInputType(arg) {
	if (arg.type === "number" || arg.type === "integer") return "number";
	if (arg.type === "email") return "email";
	if (arg.type === "url") return "url";
	return "text";
}

function isLongText(arg) {
	// Consider it long text if description mentions "text", "description", or "content"
	const name = arg.name?.toLowerCase() || "";
	return (
		name.includes("description") ||
		name.includes("content") ||
		name.includes("message") ||
		name.includes("text") ||
		name.includes("body")
	);
}

async function handleSubmit() {
	isSubmitting.value = true;

	try {
		// Build arguments object, only including non-empty values
		const args = {};
		for (const [key, value] of Object.entries(formValues.value)) {
			if (value !== "" && value !== null && value !== undefined) {
				args[key] = value;
			}
		}

		emit("submit", {
			template: props.template,
			arguments: args,
		});
	} catch (error) {
		logger.error("Error submitting template:", error);
		isSubmitting.value = false;
	}
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	background-color: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1001;
	padding: 1rem;
}

.modal-container {
	background-color: var(--ql-bg);
	border-radius: 0.75rem;
	box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
	width: 100%;
	max-width: 32rem;
	max-height: 85vh;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}

.modal-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	padding: 1.25rem 1.5rem;
	border-bottom: 1px solid var(--ql-border);
	gap: 1rem;
}

.header-info {
	display: flex;
	align-items: flex-start;
	gap: 0.75rem;
}

.template-icon {
	font-size: 1.75rem;
	line-height: 1;
}

.modal-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0;
}

.modal-subtitle {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0.25rem 0 0 0;
}

.close-btn {
	padding: 0.5rem;
	border-radius: 0.375rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	cursor: pointer;
	transition: all 0.15s ease;
	flex-shrink: 0;
}

.close-btn:hover {
	background-color: var(--ql-surface);
	color: var(--ql-text);
}

.close-btn svg {
	width: 1.25rem;
	height: 1.25rem;
}

.modal-description {
	padding: 1rem 1.5rem;
	background-color: var(--ql-surface);
	border-bottom: 1px solid var(--ql-border);
	font-size: 0.875rem;
	color: var(--ql-text-muted);
	line-height: 1.5;
}

.modal-body {
	flex: 1;
	overflow-y: auto;
	display: flex;
	flex-direction: column;
}

.form-fields {
	padding: 1.5rem;
	display: flex;
	flex-direction: column;
	gap: 1.25rem;
	flex: 1;
}

.form-field {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.field-label {
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
}

.required-indicator {
	color: #ef4444;
	margin-left: 0.25rem;
}

.field-description {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0;
	line-height: 1.4;
}

.field-input {
	width: 100%;
	padding: 0.625rem 0.75rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	background-color: var(--ql-surface);
	color: var(--ql-text);
	font-size: 0.875rem;
	transition: border-color 0.15s ease;
}

.field-input:focus {
	outline: none;
	border-color: var(--ql-accent);
}

.field-input::placeholder {
	color: var(--ql-text-muted);
}

.field-select {
	appearance: none;
	background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
	background-position: right 0.5rem center;
	background-repeat: no-repeat;
	background-size: 1.5rem 1.5rem;
	padding-right: 2.5rem;
	cursor: pointer;
}

.field-textarea {
	resize: vertical;
	min-height: 5rem;
	font-family: inherit;
}

.modal-footer {
	display: flex;
	justify-content: flex-end;
	gap: 0.75rem;
	padding: 1rem 1.5rem;
	border-top: 1px solid var(--ql-border);
	background-color: var(--ql-surface);
}

.cancel-btn {
	padding: 0.625rem 1rem;
	background-color: transparent;
	color: var(--ql-text);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	font-size: 0.875rem;
	font-weight: 500;
	cursor: pointer;
	transition: all 0.15s ease;
}

.cancel-btn:hover {
	background-color: var(--ql-bg);
}

.submit-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.625rem 1.25rem;
	background-color: var(--ql-accent);
	color: white;
	border: none;
	border-radius: 0.5rem;
	font-size: 0.875rem;
	font-weight: 500;
	cursor: pointer;
	transition: background-color 0.15s ease;
}

.submit-btn:hover:not(:disabled) {
	background-color: var(--ql-accent-hover);
}

.submit-btn:disabled {
	opacity: 0.7;
	cursor: not-allowed;
}

.spinner-small {
	width: 1rem;
	height: 1rem;
	border: 2px solid rgba(255, 255, 255, 0.3);
	border-top-color: white;
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* Responsive */
@media (max-width: 640px) {
	.modal-container {
		max-height: 90vh;
	}

	.header-info {
		flex-direction: column;
		align-items: flex-start;
	}

	.modal-footer {
		flex-direction: column-reverse;
	}

	.cancel-btn,
	.submit-btn {
		width: 100%;
		justify-content: center;
	}
}
</style>
