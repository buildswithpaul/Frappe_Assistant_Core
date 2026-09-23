<template>
	<Teleport to="body">
		<div
			v-if="modelValue"
			class="modal-overlay"
			role="dialog"
			aria-modal="true"
			aria-label="Run agent"
			@click.self="close"
		>
			<div class="modal-content">
				<h2 class="modal-title">Run Agent</h2>
				<div class="modal-field">
					<label class="field-label">Input Data (optional)</label>
					<textarea
						v-model="inputText"
						class="field-input field-textarea mono"
						placeholder="Enter input text or JSON..."
						rows="5"
					></textarea>
				</div>
				<div class="modal-actions">
					<button @click="close" class="action-btn">Cancel</button>
					<button @click="confirm" class="action-btn primary" :disabled="isRunning">
						{{ isRunning ? "Starting..." : "Run" }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
	modelValue: { type: Boolean, required: true },
	isRunning: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "confirm"]);

const inputText = ref("");

function close() {
	emit("update:modelValue", false);
}

function confirm() {
	emit("confirm", inputText.value);
	inputText.value = "";
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
	padding: 1.5rem;
	width: 100%;
	max-width: 28rem;
	box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 1.25rem;
}

.modal-field {
	margin-bottom: 1rem;
}

.field-label {
	display: block;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	margin-bottom: 0.375rem;
}

.field-input {
	width: 100%;
	padding: 0.5rem 0.75rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	box-sizing: border-box;
}

.field-input:focus {
	border-color: var(--ql-accent);
}
.field-textarea {
	resize: vertical;
	min-height: 4rem;
	font-family: inherit;
}
.field-textarea.mono {
	font-family: "SF Mono", Monaco, monospace;
	font-size: 0.8125rem;
}

.modal-actions {
	display: flex;
	justify-content: flex-end;
	gap: 0.5rem;
	margin-top: 1.25rem;
}

.action-btn {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.5rem 0.875rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border: none;
	border-radius: 0.5rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.action-btn:hover {
	background-color: var(--ql-border);
}
.action-btn.primary {
	color: white;
	background-color: var(--ql-accent);
}
.action-btn.primary:hover {
	opacity: 0.9;
}
.action-btn.primary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
</style>
