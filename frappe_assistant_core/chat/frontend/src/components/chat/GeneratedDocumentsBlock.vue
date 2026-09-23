<template>
	<div class="generated-docs-block">
		<button class="generated-docs-header" :class="{ expanded }" @click="expanded = !expanded">
			<svg
				class="generated-docs-chevron"
				:class="{ rotated: expanded }"
				viewBox="0 0 20 20"
				fill="currentColor"
				aria-hidden="true"
			>
				<path
					fill-rule="evenodd"
					d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.24 4.5a.75.75 0 01-1.08 0l-4.24-4.5a.75.75 0 01.02-1.06z"
					clip-rule="evenodd"
				/>
			</svg>
			<span class="generated-docs-label">Generated Documents</span>
			<span class="generated-docs-count">{{ items.length }}</span>
		</button>

		<ul v-show="expanded" class="generated-docs-list">
			<li v-for="item in items" :key="item.file_url" class="generated-docs-item">
				<svg
					class="generated-docs-icon"
					viewBox="0 0 20 20"
					fill="currentColor"
					aria-hidden="true"
				>
					<path
						fill-rule="evenodd"
						d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
						clip-rule="evenodd"
					/>
				</svg>
				<span class="generated-docs-name" :title="item.file_name">
					{{ item.file_name || "Untitled document" }}
				</span>
				<span v-if="item.document_type" class="generated-docs-type">
					{{ item.document_type }}
				</span>
				<span v-if="item.file_size_display" class="generated-docs-size">
					{{ item.file_size_display }}
				</span>
				<button
					class="generated-docs-open"
					:title="`Open ${item.file_name || 'document'}`"
					@click.stop="$emit('preview-document', toPreviewPayload(item))"
				>
					<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
						<path
							d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z"
						/>
						<path
							d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z"
						/>
					</svg>
					<span>Open</span>
				</button>
			</li>
		</ul>
	</div>
</template>

<script setup>
import { ref } from "vue";

defineProps({
	items: {
		type: Array,
		required: true,
	},
});

defineEmits(["preview-document"]);

const expanded = ref(true);

// Shape the payload so ChatInterface.onPreviewDocument can route a generated
// PDF through the same DocumentPreviewPanel that handles RAG citations. The
// panel reads document_type to pick the iframe branch and file_url to source
// the iframe src — document_id is omitted so the handler skips the API fetch.
function toPreviewPayload(item) {
	return {
		file_url: item.file_url,
		file_name: item.file_name,
		document_type: item.document_type || "PDF",
	};
}
</script>

<style scoped>
.generated-docs-block {
	margin-top: 0.75rem;
	padding: 0.5rem 0.75rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	background-color: var(--ql-subtle, rgba(0, 0, 0, 0.02));
}

.generated-docs-header {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	width: 100%;
	padding: 0;
	background: transparent;
	border: none;
	cursor: pointer;
	color: var(--ql-text-muted);
	font-size: 0.8125rem;
	font-weight: 500;
	text-align: left;
}

.generated-docs-header:hover {
	color: var(--ql-text);
}

.generated-docs-chevron {
	width: 0.875rem;
	height: 0.875rem;
	transition: transform 150ms ease;
	flex-shrink: 0;
}

.generated-docs-chevron.rotated {
	transform: rotate(-180deg);
}

.generated-docs-label {
	letter-spacing: 0.01em;
}

.generated-docs-count {
	padding: 0.0625rem 0.375rem;
	background-color: var(--ql-subtle);
	border-radius: 999px;
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
}

.generated-docs-list {
	list-style: none;
	margin: 0.5rem 0 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 0.25rem;
}

.generated-docs-item {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 0.375rem 0.5rem;
	border-radius: 0.375rem;
	font-size: 0.8125rem;
	color: var(--ql-text);
	transition: background-color 120ms ease;
}

.generated-docs-item:hover {
	background-color: var(--ql-subtle);
}

.generated-docs-icon {
	width: 0.9375rem;
	height: 0.9375rem;
	flex-shrink: 0;
	color: var(--ql-accent);
}

.generated-docs-name {
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.generated-docs-type {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	font-weight: 400;
}

.generated-docs-size {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	font-variant-numeric: tabular-nums;
}

.generated-docs-open {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	padding: 0.1875rem 0.5rem;
	background: transparent;
	border: 1px solid var(--ql-border);
	border-radius: 0.3125rem;
	color: var(--ql-text-muted);
	font-size: 0.75rem;
	font-weight: 500;
	cursor: pointer;
	transition: color 120ms ease, border-color 120ms ease, background-color 120ms ease;
}

.generated-docs-open:hover {
	color: var(--ql-accent);
	border-color: var(--ql-accent);
	background-color: var(--ql-subtle);
}

.generated-docs-open svg {
	width: 0.8125rem;
	height: 0.8125rem;
	flex-shrink: 0;
}
</style>
