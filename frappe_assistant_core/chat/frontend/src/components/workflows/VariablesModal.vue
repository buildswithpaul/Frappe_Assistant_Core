<template>
	<Teleport to="body">
		<div
			v-if="modelValue"
			class="modal-overlay"
			role="dialog"
			aria-modal="true"
			aria-label="Agent variables"
			@click.self="close"
		>
			<div class="modal-content modal-variables">
				<div class="modal-title-row">
					<h2 class="modal-title">Agent Variables</h2>
					<button
						@click="addVariable"
						class="add-var-btn"
						title="Add variable"
						aria-label="Add variable"
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
								d="M12 4v16m8-8H4"
							/>
						</svg>
					</button>
				</div>
				<p class="modal-hint">
					Variables are available in system prompts and transform templates as
					<code v-pre>{{ variable_name }}</code> placeholders.
				</p>

				<div v-if="editVariables.length === 0" class="variables-empty">
					No variables defined. Click + to add one.
				</div>

				<div v-else class="variables-list">
					<div v-for="(v, i) in editVariables" :key="i" class="variable-row">
						<input
							v-model="v.key"
							class="field-input var-key"
							placeholder="variable_name"
							@input="v.key = v.key.replace(/[^a-zA-Z0-9_]/g, '')"
						/>
						<input
							v-model="v.value"
							class="field-input var-value"
							placeholder="value"
						/>
						<button
							@click="editVariables.splice(i, 1)"
							class="var-delete-btn"
							title="Remove"
							aria-label="Remove variable"
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
				</div>

				<div class="modal-actions">
					<button @click="close" class="action-btn">Cancel</button>
					<button @click="save" class="action-btn primary">Save</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { ref, watch } from "vue";

const props = defineProps({
	modelValue: { type: Boolean, required: true },
	variables: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["update:modelValue", "save"]);

const editVariables = ref([]);

// Populate edit list from variables prop when modal opens
watch(
	() => props.modelValue,
	(open) => {
		if (open) {
			const vars = props.variables || {};
			editVariables.value = Object.entries(vars).map(([key, value]) => ({
				key,
				value: String(value),
			}));
		}
	}
);

function addVariable() {
	editVariables.value.push({ key: "", value: "" });
}

function save() {
	const vars = {};
	for (const v of editVariables.value) {
		const key = v.key.trim();
		if (key) vars[key] = v.value;
	}
	emit("save", vars);
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
	padding: 1.5rem;
	width: 100%;
	max-width: 28rem;
	box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-variables {
	max-width: 32rem;
}

.modal-title {
	font-size: 1.125rem;
	font-weight: 600;
	color: var(--ql-text);
	margin: 0 0 1.25rem;
}

.modal-title-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 0.5rem;
}

.modal-title-row .modal-title {
	margin: 0;
}

.add-var-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 1.75rem;
	height: 1.75rem;
	color: var(--ql-accent);
	background: var(--ql-accent-soft);
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: background 0.15s ease;
}

.add-var-btn:hover {
	background: var(--ql-accent-soft);
}

.modal-hint {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin: 0 0 1rem;
	line-height: 1.4;
}

.modal-hint code {
	background: var(--ql-subtle);
	padding: 0.0625rem 0.25rem;
	border-radius: 0.1875rem;
	font-size: 0.6875rem;
}

.variables-empty {
	padding: 1.5rem;
	text-align: center;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
}

.variables-list {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
	max-height: 300px;
	overflow-y: auto;
}

.variable-row {
	display: flex;
	gap: 0.375rem;
	align-items: center;
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

.var-key {
	flex: 0 0 40%;
	font-family: "SF Mono", Monaco, monospace;
	font-size: 0.8125rem;
}

.var-value {
	flex: 1;
	min-width: 0;
}

.var-delete-btn {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	width: 1.5rem;
	height: 1.5rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.var-delete-btn:hover {
	color: var(--ql-danger);
	background: rgba(239, 68, 68, 0.1);
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
