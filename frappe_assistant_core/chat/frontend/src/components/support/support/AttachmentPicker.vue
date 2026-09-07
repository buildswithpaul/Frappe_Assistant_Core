<template>
	<div class="attachment-picker">
		<div
			data-test="dropzone"
			class="dropzone"
			:class="{ dragging, disabled }"
			@dragover.prevent="onDragOver"
			@dragleave.prevent="dragging = false"
			@drop.prevent="onDrop"
		>
			<button
				type="button"
				class="attach-btn"
				:disabled="disabled || files.length >= maxFiles"
				@click="onPick"
			>
				📎 Attach
			</button>
			<span class="hint">Drop, paste, or attach — images or PDF, up to {{ maxFiles }}.</span>
			<input
				ref="input"
				type="file"
				class="hidden-input"
				multiple
				:accept="accept"
				@change="onChange"
			/>
		</div>

		<ul v-if="files.length" class="chips">
			<li v-for="(f, i) in files" :key="f.id" class="chip" :class="f.status">
				<img v-if="f.is_image && f.previewUrl" class="thumb" :src="f.previewUrl" :alt="f.file_name" />
				<span v-else class="pdf-icon" aria-hidden="true">📄</span>
				<span class="chip-name">{{ f.file_name }}</span>
				<span v-if="f.status === 'uploading'" class="spinner" aria-label="Uploading"></span>
				<button
					v-if="f.status === 'error'"
					type="button"
					data-test="retry"
					class="retry"
					@click="$emit('retry', i)"
				>
					Retry
				</button>
				<button
					type="button"
					data-test="remove"
					class="remove"
					aria-label="Remove attachment"
					@click="$emit('remove', i)"
				>
					×
				</button>
				<span v-if="f.status === 'error'" class="chip-error">{{ f.error }}</span>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { TICKET_ACCEPT, TICKET_MAX_FILES } from "@/composables/useTicketAttachments.js";

const props = defineProps({
	files: { type: Array, default: () => [] },
	disabled: { type: Boolean, default: false },
	maxFiles: { type: Number, default: TICKET_MAX_FILES },
});
const emit = defineEmits(["add", "remove", "retry"]);

const accept = TICKET_ACCEPT;
const input = ref(null);
const dragging = ref(false);

function onPick() {
	if (!props.disabled) input.value?.click();
}

function onChange(e) {
	const list = Array.from(e.target.files || []);
	if (list.length) emit("add", list);
	e.target.value = "";
}

function onDragOver() {
	if (!props.disabled) dragging.value = true;
}

function onDrop(e) {
	dragging.value = false;
	if (props.disabled) return;
	const list = Array.from(e.dataTransfer?.files || []);
	if (list.length) emit("add", list);
}
</script>

<style scoped>
.attachment-picker { display: flex; flex-direction: column; gap: var(--ql-space-2); }
.dropzone {
	display: flex; align-items: center; gap: var(--ql-space-2); flex-wrap: wrap;
	padding: var(--ql-space-2) var(--ql-space-3); border: 1px dashed var(--ql-border);
	border-radius: var(--ql-radius-sm); background: var(--ql-subtle);
	transition: border-color 0.15s ease, background 0.15s ease;
}
.dropzone.dragging { border-color: var(--ql-accent); background: var(--ql-accent-soft); }
.dropzone.disabled { opacity: 0.6; }
.attach-btn {
	padding: var(--ql-space-1) var(--ql-space-3); border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm); background: var(--ql-surface); color: var(--ql-text);
	cursor: pointer; font: inherit; font-size: 0.85rem;
}
.attach-btn:hover:not(:disabled) { border-color: var(--ql-border-hover); }
.attach-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.hint { font-size: 0.78rem; color: var(--ql-text-muted); }
.hidden-input { display: none; }

.chips { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--ql-space-2); }
.chip {
	position: relative; display: flex; align-items: center; gap: var(--ql-space-1);
	padding: var(--ql-space-1) var(--ql-space-2); border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm); background: var(--ql-surface); max-width: 200px;
}
.chip.error { border-color: var(--ql-danger); }
.thumb { width: 32px; height: 32px; object-fit: cover; border-radius: 4px; flex-shrink: 0; }
.pdf-icon { font-size: 1.1rem; flex-shrink: 0; }
.chip-name {
	font-size: 0.78rem; color: var(--ql-text); overflow: hidden; text-overflow: ellipsis;
	white-space: nowrap; flex: 1;
}
.chip-error { font-size: 0.72rem; color: var(--ql-danger); width: 100%; }
.remove, .retry { border: none; background: none; cursor: pointer; color: var(--ql-text-muted); font: inherit; }
.remove { font-size: 1.1rem; line-height: 1; }
.remove:hover { color: var(--ql-danger); }
.retry { font-size: 0.72rem; color: var(--ql-accent); }
.spinner {
	width: 12px; height: 12px; border: 2px solid var(--ql-border); border-top-color: var(--ql-accent);
	border-radius: 50%; animation: ap-spin 0.7s linear infinite; flex-shrink: 0;
}
@keyframes ap-spin { to { transform: rotate(360deg); } }
</style>
