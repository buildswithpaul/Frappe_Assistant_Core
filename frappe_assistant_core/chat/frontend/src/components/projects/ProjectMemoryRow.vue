<template>
	<li class="memory-row" data-test="memory-row">
		<span class="pill" :class="`type-${memory.memory_type}`" data-test="memory-type">{{ typeLabel }}</span>
		<div v-if="editing" class="editor">
			<textarea
				v-model="draft"
				class="edit-textarea"
				rows="2"
				maxlength="500"
				:aria-label="__('Memory text')"
				data-test="memory-edit-input"
				@keydown.enter="onEnter"
				@keydown.esc="cancel"
			/>
			<div class="actions">
				<button
					class="text-btn primary"
					data-test="memory-edit-save"
					:disabled="!canSave"
					@click="save"
				>
					{{ __("Save") }}
				</button>
				<button class="text-btn" data-test="memory-edit-cancel" @click="cancel">{{ __("Cancel") }}</button>
			</div>
		</div>
		<template v-else>
			<span class="content" data-test="memory-content">{{ memory.content }}</span>
			<button class="text-btn" :aria-label="__('Edit memory')" data-test="memory-edit" @click="start">
				{{ __("Edit") }}
			</button>
			<button
				class="text-btn danger"
				:aria-label="__('Delete memory')"
				data-test="memory-delete"
				@click="$emit('delete')"
			>
				{{ __("Delete") }}
			</button>
		</template>
	</li>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";

const props = defineProps({
	memory: { type: Object, required: true },
});

const emit = defineEmits(["edit", "delete"]);

const editing = ref(false);
const draft = ref("");

const typeLabel = computed(() => {
	const labels = {
		preference: __("Preference"),
		fact: __("Fact"),
		summary: __("Summary"),
		correction: __("Correction"),
	};
	return labels[props.memory.memory_type] || labels.fact;
});

const canSave = computed(() => draft.value.trim() && draft.value.trim() !== props.memory.content);

function start() {
	draft.value = props.memory.content;
	editing.value = true;
}

function cancel() {
	editing.value = false;
}

function onEnter(event) {
	// Enter that confirms an IME composition belongs to the composition, not to Save.
	if (event.isComposing) return;
	event.preventDefault();
	save();
}

// The editor closes only once the parent reports the save landed, so a failed
// save keeps the draft.
function save() {
	if (!canSave.value) return;
	emit("edit", {
		memoryId: props.memory.memory_id,
		content: draft.value.trim(),
		onSaved: () => (editing.value = false),
	});
}
</script>

<style scoped>
.memory-row {
	display: flex;
	align-items: flex-start;
	gap: 0.625rem;
	padding: 0.375rem 0;
	font-size: 0.875rem;
	color: var(--ql-text);
}

.content {
	flex: 1;
	min-width: 0;
	line-height: 1.5;
	overflow-wrap: anywhere;
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

.pill.type-preference {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}

.pill.type-correction {
	color: var(--ql-danger);
}

.editor {
	flex: 1;
	min-width: 0;
}

.edit-textarea {
	display: block;
	width: 100%;
	padding: 0.5rem;
	font-size: 0.875rem;
	font-family: inherit;
	line-height: 1.5;
	color: var(--ql-text);
	background: var(--ql-bg);
	border: 1px solid var(--ql-accent);
	border-radius: 0.375rem;
	resize: vertical;
	outline: none;
}

.actions {
	display: flex;
	gap: 0.375rem;
	margin-top: 0.375rem;
}

.text-btn {
	flex-shrink: 0;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.25rem;
	padding: 0.125rem 0.375rem;
	cursor: pointer;
}

.text-btn:hover:not(:disabled) {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.text-btn.primary {
	color: var(--ql-accent);
}

.text-btn.danger {
	color: var(--ql-danger);
}

.text-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}
</style>
