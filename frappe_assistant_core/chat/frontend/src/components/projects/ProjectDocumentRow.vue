<template>
	<li class="doc-row" data-test="doc-row">
		<button
			class="doc-open"
			data-test="doc-preview"
			:title="__('Preview {0}', [doc.file_name])"
			@click="$emit('preview')"
		>
			<span class="doc-name">{{ doc.file_name }}</span>
			<span class="doc-size">{{ formatFileSizeMb(doc.file_size_mb) }}</span>
		</button>
		<span class="pill" :class="status.cls" data-test="doc-status">{{ status.label }}</span>
		<div class="row-actions">
			<a
				class="row-action"
				data-test="doc-download"
				:href="api.documents.getDownloadUrl(doc.document_id)"
				:title="__('Download')"
				:aria-label="__('Download {0}', [doc.file_name])"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
					/>
				</svg>
			</a>
			<button
				class="row-action danger"
				data-test="doc-delete"
				:title="__('Delete')"
				:aria-label="__('Delete {0}', [doc.file_name])"
				@click="$emit('delete')"
			>
				<svg fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
					/>
				</svg>
			</button>
		</div>
	</li>
</template>

<script setup>
import { computed } from "vue";
import { api } from "@/api/client";
import { formatFileSizeMb } from "@/composables/useFormatters";
import { __ } from "@/utils/i18n";

const props = defineProps({
	doc: { type: Object, required: true },
});

defineEmits(["preview", "delete"]);

const STATUS_BY_STATE = {
	Completed: { label: "Ready", cls: "ready" },
	Failed: { label: "Failed", cls: "failed" },
};

const status = computed(() => {
	const entry = STATUS_BY_STATE[props.doc.embedding_status] || { label: "Processing", cls: "processing" };
	return { cls: entry.cls, label: __(entry.label) };
});
</script>

<style scoped>
.doc-row {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.125rem 0;
	font-size: 0.875rem;
	color: var(--ql-text);
}

.doc-open {
	flex: 1;
	min-width: 0;
	display: flex;
	align-items: center;
	gap: 0.625rem;
	padding: 0.375rem 0.5rem;
	margin-left: -0.5rem;
	font: inherit;
	color: inherit;
	text-align: left;
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.doc-open:hover,
.doc-open:focus-visible {
	background-color: var(--ql-subtle);
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

.row-actions {
	display: flex;
	flex-shrink: 0;
	gap: 0.125rem;
	opacity: 0;
	transition: opacity 0.15s ease;
}

.doc-row:hover .row-actions,
.row-actions:focus-within {
	opacity: 1;
}

@media (hover: none) {
	.row-actions {
		opacity: 1;
	}
}

.row-action {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 1.75rem;
	height: 1.75rem;
	padding: 0.3125rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
}

.row-action svg {
	width: 100%;
	height: 100%;
}

.row-action:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}

.row-action.danger:hover {
	color: var(--ql-danger);
}
</style>
