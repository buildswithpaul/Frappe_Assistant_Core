<template>
	<div v-if="visible" class="markdown-preview">
		<div class="preview-header">
			<svg class="preview-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
				/>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
				/>
			</svg>
			<span>Preview</span>
		</div>
		<div class="preview-content" v-html="html"></div>
	</div>
</template>

<script setup>
defineProps({
	visible: { type: Boolean, default: false },
	html: { type: String, default: "" },
});
</script>

<style scoped>
.markdown-preview {
	margin-bottom: 0.625rem;
	padding: 0.75rem 1rem;
	background: var(--ql-subtle);
	border-radius: 0.75rem;
	border: 1px solid var(--ql-border);
	max-height: 200px;
	overflow-y: auto;
}

.preview-header {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	margin-bottom: 0.5rem;
	padding-bottom: 0.5rem;
	border-bottom: 1px solid var(--ql-border);
}

.preview-icon {
	width: 0.875rem;
	height: 0.875rem;
}

.preview-content {
	font-size: 0.875rem;
	line-height: 1.6;
	color: var(--ql-text);
}

.preview-content :deep(p) {
	margin-bottom: 0.5rem;
}
.preview-content :deep(p:last-child) {
	margin-bottom: 0;
}

.preview-content :deep(ul),
.preview-content :deep(ol) {
	margin-bottom: 0.5rem;
	padding-left: 1.25rem;
}

.preview-content :deep(ul) {
	list-style: disc;
}

.preview-content :deep(ol) {
	list-style: decimal;
}

.preview-content :deep(li) {
	margin-bottom: 0.125rem;
}

.preview-content :deep(code) {
	padding: 0.125rem 0.25rem;
	background-color: rgba(0, 0, 0, 0.1);
	border-radius: 0.25rem;
	font-size: 0.8125em;
	font-family: "SF Mono", "Monaco", "Cascadia Code", monospace;
}

.preview-content :deep(pre) {
	margin: 0.5rem 0;
	padding: 0.75rem;
	background-color: #1e293b;
	border-radius: 0.375rem;
	overflow-x: auto;
}

.preview-content :deep(pre code) {
	padding: 0;
	background: transparent;
	color: #e2e8f0;
	font-size: 0.8125rem;
}

.preview-content :deep(strong) {
	font-weight: 600;
}
.preview-content :deep(em) {
	font-style: italic;
}

.preview-content :deep(a) {
	color: var(--ql-accent);
	text-decoration: underline;
}

.preview-content :deep(blockquote) {
	margin: 0.5rem 0;
	padding-left: 0.75rem;
	border-left: 3px solid var(--ql-accent);
	color: var(--ql-text-muted);
}

.preview-content :deep(h1),
.preview-content :deep(h2),
.preview-content :deep(h3),
.preview-content :deep(h4),
.preview-content :deep(h5),
.preview-content :deep(h6) {
	font-weight: 600;
	margin-bottom: 0.5rem;
}

.preview-content :deep(h1) {
	font-size: 1.25rem;
}
.preview-content :deep(h2) {
	font-size: 1.125rem;
}
.preview-content :deep(h3) {
	font-size: 1rem;
}

.preview-content :deep(table) {
	width: 100%;
	margin: 0.5rem 0;
	border-collapse: collapse;
	font-size: 0.8125rem;
	display: block;
	overflow-x: auto;
}

.preview-content :deep(th),
.preview-content :deep(td) {
	padding: 0.375rem 0.5rem;
	border: 1px solid var(--ql-border);
	text-align: left;
}

.preview-content :deep(th) {
	background-color: var(--ql-subtle);
	font-weight: 600;
}

[data-theme="dark"] .markdown-preview,
.dark .markdown-preview {
	background: rgba(255, 255, 255, 0.03);
	border-color: rgba(255, 255, 255, 0.1);
}

[data-theme="dark"] .preview-content :deep(code),
.dark .preview-content :deep(code) {
	background-color: rgba(255, 255, 255, 0.1);
}
</style>
