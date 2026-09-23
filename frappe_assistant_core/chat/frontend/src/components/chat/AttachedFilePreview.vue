<template>
	<div v-if="files.length > 0" class="file-preview-row">
		<div v-for="(file, index) in files" :key="index" class="file-preview">
			<svg class="file-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
				/>
			</svg>
			<span class="file-name">{{ file.name }}</span>
			<span class="file-size">{{ formatFileSize(file.size) }}</span>
			<button @click="$emit('remove', index)" class="file-remove" aria-label="Remove file">
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
</template>

<script setup>
import { formatFileSize } from "@/composables/useFormatters";

defineProps({
	files: { type: Array, default: () => [] },
});
defineEmits(["remove"]);
</script>

<style scoped>
.file-preview-row {
	display: flex;
	flex-wrap: wrap;
	gap: 0.5rem;
	margin-bottom: 0.625rem;
}

.file-preview {
	display: inline-flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.375rem 0.625rem;
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
}

.file-icon {
	width: 0.875rem;
	height: 0.875rem;
	color: var(--ql-text-muted);
	flex-shrink: 0;
}

.file-name {
	max-width: 180px;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.file-size {
	color: var(--ql-text-muted);
	font-size: 0.75rem;
}

.file-remove {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 1rem;
	height: 1rem;
	color: var(--ql-text-muted);
	border-radius: 0.25rem;
	transition: all 0.15s ease;
}

.file-remove:hover {
	color: var(--ql-danger);
	background: rgba(239, 68, 68, 0.1);
}

.file-remove svg {
	width: 0.875rem;
	height: 0.875rem;
}
</style>
