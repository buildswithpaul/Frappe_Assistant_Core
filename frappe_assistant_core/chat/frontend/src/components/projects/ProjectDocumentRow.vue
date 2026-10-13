<template>
	<li class="doc-row" data-test="doc-row">
		<span class="doc-name" :title="doc.file_name">{{ doc.file_name }}</span>
		<span class="doc-size">{{ formatFileSize(doc.file_size || 0) }}</span>
		<span class="pill" :class="status.cls" data-test="doc-status">{{ status.label }}</span>
		<div class="doc-menu-root">
			<button
				class="row-menu"
				data-test="doc-menu"
				aria-haspopup="menu"
				:aria-expanded="menuOpen"
				:aria-label="__('Document options')"
				@click="$emit('toggle-menu')"
			>
				⋯
			</button>
			<div v-if="menuOpen" class="menu" role="menu" @keydown.esc.stop.prevent="$emit('close-menu')">
				<a
					class="menu-item"
					role="menuitem"
					data-test="doc-download"
					:href="api.documents.getDownloadUrl(doc.document_id)"
					@click="$emit('close-menu')"
				>
					{{ __("Download") }}
				</a>
				<button class="menu-item danger" role="menuitem" data-test="doc-delete" @click="$emit('delete')">
					{{ __("Delete") }}
				</button>
			</div>
		</div>
	</li>
</template>

<script setup>
import { computed } from "vue";
import { api } from "@/api/client";
import { formatFileSize } from "@/composables/useFormatters";
import { __ } from "@/utils/i18n";

const props = defineProps({
	doc: { type: Object, required: true },
	menuOpen: { type: Boolean, default: false },
});

defineEmits(["toggle-menu", "close-menu", "delete"]);

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
	gap: 0.625rem;
	padding: 0.375rem 0;
	font-size: 0.875rem;
	color: var(--ql-text);
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

.doc-menu-root {
	position: relative;
	flex-shrink: 0;
}

.row-menu {
	padding: 0.25rem 0.5rem;
	color: var(--ql-text-muted);
	background: none;
	border: none;
	border-radius: 0.25rem;
	cursor: pointer;
	opacity: 0;
	transition: all 0.15s ease;
}

.doc-row:hover .row-menu,
.row-menu:focus-visible,
.row-menu[aria-expanded="true"] {
	opacity: 1;
}

@media (hover: none) {
	.row-menu {
		opacity: 1;
	}
}

.row-menu:hover {
	color: var(--ql-text);
	background-color: var(--ql-subtle);
}

.menu {
	position: absolute;
	right: 0;
	top: 100%;
	z-index: 20;
	min-width: 9rem;
	padding: 0.25rem;
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.menu-item {
	display: block;
	width: 100%;
	box-sizing: border-box;
	text-align: left;
	padding: 0.375rem 0.625rem;
	font-size: 0.875rem;
	color: var(--ql-text);
	background: none;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	text-decoration: none;
}

.menu-item:hover {
	background-color: var(--ql-subtle);
}

.menu-item.danger {
	color: var(--ql-danger);
}
</style>
