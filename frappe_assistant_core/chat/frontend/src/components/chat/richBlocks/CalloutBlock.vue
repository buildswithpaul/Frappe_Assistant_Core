<template>
	<div class="callout-block" :class="`callout-${calloutType}`">
		<div class="callout-icon">
			<!-- Info -->
			<svg
				v-if="calloutType === 'info'"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<!-- Warning -->
			<svg
				v-else-if="calloutType === 'warning'"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
				/>
			</svg>
			<!-- Tip -->
			<svg
				v-else-if="calloutType === 'tip'"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
				/>
			</svg>
			<!-- Success -->
			<svg
				v-else-if="calloutType === 'success'"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<!-- Error -->
			<svg v-else fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
		</div>
		<div class="callout-content">
			<div v-if="title" class="callout-title">{{ title }}</div>
			<div v-if="body" class="callout-body" v-html="renderedBody"></div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

const props = defineProps({
	type: { type: String, default: "info" },
	title: { type: String, default: "" },
	body: { type: String, default: "" },
});

const validTypes = ["info", "warning", "tip", "success", "error"];
const calloutType = computed(() => (validTypes.includes(props.type) ? props.type : "info"));

const renderedBody = computed(() => {
	if (!props.body) return "";
	return DOMPurify.sanitize(marked.parse(props.body));
});
</script>

<style scoped>
.callout-block {
	display: flex;
	gap: 0.75rem;
	padding: 0.875rem 1rem;
	border-radius: 0.5rem;
	border-left: 3px solid;
	margin: 0.75rem 0;
}

.callout-icon {
	flex-shrink: 0;
	width: 1.25rem;
	height: 1.25rem;
	margin-top: 0.125rem;
}

.callout-icon svg {
	width: 100%;
	height: 100%;
}

.callout-content {
	flex: 1;
	min-width: 0;
}

.callout-title {
	font-weight: 600;
	font-size: 0.875rem;
	margin-bottom: 0.25rem;
}

.callout-body {
	font-size: 0.8125rem;
	line-height: 1.5;
}

.callout-body :deep(p) {
	margin: 0;
}
.callout-body :deep(p + p) {
	margin-top: 0.375rem;
}
.callout-body :deep(strong) {
	font-weight: 600;
}
.callout-body :deep(a) {
	text-decoration: underline;
}
.callout-body :deep(ul),
.callout-body :deep(ol) {
	margin: 0.375rem 0;
	padding-left: 1.25rem;
}
.callout-body :deep(ul) {
	list-style: disc;
}
.callout-body :deep(ol) {
	list-style: decimal;
}
.callout-body :deep(li) {
	margin-bottom: 0.25rem;
}

/* Info - Teal (brand/info color) */
.callout-info {
	background: var(--ql-accent-soft);
	border-left-color: var(--ql-accent);
	color: var(--ql-accent-hover);
}
.callout-info .callout-icon {
	color: var(--ql-accent);
}

/* Warning - Amber */
.callout-warning {
	background: rgba(245, 158, 11, 0.08);
	border-left-color: #f59e0b;
	color: #92400e;
}
.callout-warning .callout-icon {
	color: #f59e0b;
}

/* Tip - Emerald */
.callout-tip {
	background: rgba(16, 185, 129, 0.08);
	border-left-color: #10b981;
	color: #065f46;
}
.callout-tip .callout-icon {
	color: #10b981;
}

/* Success - Green */
.callout-success {
	background: rgba(34, 197, 94, 0.08);
	border-left-color: #22c55e;
	color: #166534;
}
.callout-success .callout-icon {
	color: #22c55e;
}

/* Error - Red */
.callout-error {
	background: rgba(239, 68, 68, 0.08);
	border-left-color: #ef4444;
	color: #991b1b;
}
.callout-error .callout-icon {
	color: #ef4444;
}
</style>
