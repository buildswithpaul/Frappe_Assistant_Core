<template>
	<div class="tab-content">
		<div class="form-field">
			<label class="field-label">Name</label>
			<input
				v-model="name"
				class="field-input"
				placeholder="e.g., Daily Report Generator"
				@keydown.enter="handleCreate"
				ref="nameRef"
			/>
		</div>
		<div class="form-field">
			<label class="field-label">Description <span class="optional">(optional)</span></label>
			<textarea
				v-model="description"
				class="field-input field-textarea"
				placeholder="What does this agent do?"
				rows="3"
			></textarea>
		</div>
		<div class="form-actions">
			<button @click="$emit('cancel')" class="action-btn">Cancel</button>
			<button
				@click="handleCreate"
				class="action-btn primary"
				:disabled="!name.trim() || isBusy"
			>
				{{ isBusy ? "Creating..." : "Create" }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref, watch, nextTick } from "vue";

const props = defineProps({
	visible: { type: Boolean, default: false },
	isBusy: { type: Boolean, default: false },
});

const emit = defineEmits(["cancel", "create"]);

const name = ref("");
const description = ref("");
const nameRef = ref(null);

watch(
	() => props.visible,
	async (val) => {
		if (val) {
			name.value = "";
			description.value = "";
			await nextTick();
			nameRef.value?.focus();
		}
	}
);

function handleCreate() {
	if (!name.value.trim() || props.isBusy) return;
	emit("create", { name: name.value.trim(), description: description.value.trim() });
}
</script>

<style scoped>
.tab-content {
	padding: 1.25rem;
	overflow-y: auto;
	flex: 1;
	min-height: 0;
}

.form-field {
	margin-bottom: 1rem;
}

.field-label {
	display: block;
	font-size: 0.8125rem;
	font-weight: 500;
	color: var(--ql-text);
	margin-bottom: 0.375rem;
}

.field-label .optional {
	font-weight: 400;
	color: var(--ql-text-muted);
	font-size: 0.75rem;
}

.field-input {
	width: 100%;
	padding: 0.5rem 0.75rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	outline: none;
	transition: border-color 0.15s ease;
	box-sizing: border-box;
}

.field-input:focus {
	border-color: var(--ql-accent);
}

.field-textarea {
	resize: vertical;
	min-height: 3.5rem;
	font-family: inherit;
	line-height: 1.5;
}

.form-actions {
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
	background-color: var(--ql-accent-hover);
}

.action-btn.primary:disabled {
	opacity: 0.6;
	cursor: not-allowed;
}
</style>
