<template>
	<div
		class="thinking-block"
		:class="{
			'thinking-streaming': block.isStreaming,
			'thinking-expanded': block.isExpanded,
		}"
	>
		<!-- Collapsible Header -->
		<button
			class="thinking-header"
			@click="$emit('toggle', block.id)"
			:aria-expanded="block.isExpanded"
		>
			<!-- Thinking Icon -->
			<div class="thinking-icon">
				<svg
					v-if="block.isStreaming"
					class="thinking-spinner"
					viewBox="0 0 24 24"
					fill="none"
				>
					<circle
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="2"
						opacity="0.25"
					/>
					<path
						d="M12 2a10 10 0 0 1 10 10"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
					/>
				</svg>
				<svg
					v-else
					class="thought-icon"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
					/>
				</svg>
			</div>

			<!-- Summary Text -->
			<span class="thinking-summary">
				<template v-if="block.isStreaming">Thinking...</template>
				<template v-else>{{ summaryText }}</template>
			</span>

			<!-- Duration -->
			<span v-if="duration" class="thinking-duration">{{ duration }}</span>

			<!-- Chevron -->
			<svg
				class="thinking-chevron"
				:class="{ 'chevron-expanded': block.isExpanded }"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9 5l7 7-7 7"
				/>
			</svg>
		</button>

		<!-- Expanded Content -->
		<div v-if="block.isExpanded" class="thinking-content">
			<div class="thinking-text" v-html="renderedContent"></div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

const props = defineProps({
	block: {
		type: Object,
		required: true,
	},
});

defineEmits(["toggle"]);

// Extract a meaningful summary from thinking content
const summaryText = computed(() => {
	const content = (props.block.content || "").trim();
	if (!content) return "Thought about the request";

	// Take the first line or first sentence
	const firstLine = content.split("\n")[0].trim();

	// If the first line is short enough, use it
	if (firstLine.length <= 100) return firstLine;

	// Otherwise truncate at a word boundary
	const truncated = firstLine.substring(0, 100);
	const lastSpace = truncated.lastIndexOf(" ");
	return (lastSpace > 40 ? truncated.substring(0, lastSpace) : truncated) + "...";
});

// Render markdown for expanded view
const renderedContent = computed(() => {
	const content = props.block.content || "";
	if (!content) return "";
	return DOMPurify.sanitize(marked.parse(content));
});

// Calculate duration
const duration = computed(() => {
	if (props.block.isStreaming || !props.block.startTime || !props.block.endTime) return null;

	const start = new Date(props.block.startTime);
	const end = new Date(props.block.endTime);
	const diffMs = end - start;

	if (diffMs < 1000) return `${diffMs}ms`;
	if (diffMs < 60000) return `${(diffMs / 1000).toFixed(1)}s`;
	const mins = Math.floor(diffMs / 60000);
	const secs = Math.floor((diffMs % 60000) / 1000);
	return `${mins}m ${secs}s`;
});
</script>

<style scoped>
.thinking-block {
	margin: 0.125rem 0;
	border-radius: 0.375rem;
	overflow: hidden;
	transition: background-color 0.2s ease;
}

.thinking-block.thinking-streaming {
	background-color: var(--ql-accent-soft);
}

.thinking-header {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	width: 100%;
	padding: 0.375rem 0.25rem;
	background: transparent;
	border: none;
	cursor: pointer;
	text-align: left;
	color: var(--ql-text-muted, #9ca3af);
	transition: color 0.15s ease;
}

.thinking-header:hover {
	color: var(--ql-text-secondary, #6b7280);
}

.thinking-icon {
	flex-shrink: 0;
	width: 0.875rem;
	height: 0.875rem;
	color: var(--ql-text-muted, #9ca3af);
}

.thinking-icon svg {
	width: 100%;
	height: 100%;
}

.thinking-spinner {
	animation: spin 1s linear infinite;
}

@keyframes spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

.thinking-summary {
	flex: 1;
	font-size: 0.8125rem;
	color: var(--ql-text-muted, #9ca3af);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.thinking-streaming .thinking-summary {
	font-style: italic;
	color: var(--ql-text-secondary, #6b7280);
}

.thinking-duration {
	flex-shrink: 0;
	font-size: 0.6875rem;
	color: var(--ql-text-muted, #9ca3af);
	opacity: 0.7;
}

.thinking-chevron {
	flex-shrink: 0;
	width: 0.75rem;
	height: 0.75rem;
	color: var(--ql-text-muted, #9ca3af);
	transition: transform 0.2s ease;
	opacity: 0.6;
}

.thinking-chevron.chevron-expanded {
	transform: rotate(90deg);
}

.thinking-content {
	padding: 0.375rem 0.25rem 0.5rem 1.5rem;
	border-left: 2px solid var(--ql-border, rgba(156, 163, 175, 0.2));
	margin-left: 0.4375rem;
	max-height: 24rem;
	overflow-y: auto;
}

/* Rendered markdown in thinking content */
.thinking-text {
	font-size: 0.8125rem;
	line-height: 1.6;
	color: var(--ql-text-muted, #9ca3af);
	word-break: break-word;
}

.thinking-text :deep(p) {
	margin-bottom: 0.5rem;
}

.thinking-text :deep(p:last-child) {
	margin-bottom: 0;
}

.thinking-text :deep(ul),
.thinking-text :deep(ol) {
	margin-bottom: 0.5rem;
	padding-left: 1.25rem;
}

.thinking-text :deep(ul) {
	list-style: disc;
}

.thinking-text :deep(ol) {
	list-style: decimal;
}

.thinking-text :deep(li) {
	margin-bottom: 0.125rem;
}

.thinking-text :deep(code) {
	padding: 0.0625rem 0.25rem;
	background-color: rgba(0, 0, 0, 0.06);
	border-radius: 0.1875rem;
	font-size: 0.8em;
	font-family: "SF Mono", "Monaco", "Cascadia Code", monospace;
}

.thinking-text :deep(pre) {
	margin: 0.5rem 0;
	padding: 0.5rem;
	background-color: rgba(0, 0, 0, 0.04);
	border-radius: 0.375rem;
	overflow-x: auto;
}

.thinking-text :deep(pre code) {
	padding: 0;
	background: transparent;
	font-size: 0.75rem;
}

.thinking-text :deep(strong) {
	font-weight: 600;
}

.thinking-text :deep(blockquote) {
	margin: 0.5rem 0;
	padding-left: 0.75rem;
	border-left: 2px solid var(--ql-text-muted, #9ca3af);
	opacity: 0.85;
}
</style>
