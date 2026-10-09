<template>
	<div class="run-details">
		<div class="details-divider"></div>

		<div v-if="renderedResult" class="run-result">
			<div class="result-label">{{ __("Result") }}</div>
			<div class="result-body markdown-body" v-html="renderedResult"></div>
		</div>

		<SkippedActionsList :items="skipped" :node-runs="run.node_runs || []" />

		<div v-if="run.error_message" class="detail-error-full" role="alert">
			{{ run.error_message.trim() }}
		</div>

		<RunNodeDetail v-for="nr in run.node_runs || []" :key="nr.node_id" :node-run="nr" />

		<div v-if="!run.node_runs?.length" class="no-nodes-msg">
			{{ __("No nodes were executed in this run.") }}
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { __ } from "@/utils/i18n";
import RunNodeDetail from "../RunNodeDetail.vue";
import SkippedActionsList from "./SkippedActionsList.vue";
import { parseSkippedActions } from "./runFormat";

const props = defineProps({
	run: { type: Object, required: true },
});

const skipped = computed(() => parseSkippedActions(props.run));

const renderedResult = computed(() => {
	const data = props.run;
	if (data.status !== "Completed" || !data.output_data) return "";
	return DOMPurify.sanitize(marked.parse(data.output_data));
});
</script>

<style scoped>
.details-divider {
	height: 1px;
	background: var(--ql-border);
	margin: 0.5rem 0;
}

.detail-error-full {
	font-size: 0.75rem;
	color: var(--ql-danger);
	line-height: 1.4;
	padding: 0.5rem;
	background: color-mix(in srgb, var(--ql-danger) 8%, transparent);
	border-radius: var(--ql-radius-sm);
	word-break: break-word;
	margin-bottom: 0.5rem;
}

.run-result {
	margin-bottom: 0.5rem;
}

.result-label {
	font-size: 0.625rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: var(--ql-text-muted);
	margin-bottom: 0.25rem;
}

.result-body {
	font-size: 0.75rem;
	line-height: 1.5;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border-radius: var(--ql-radius-sm);
	padding: 0.5rem 0.625rem;
	max-height: 280px;
	overflow-y: auto;
	word-break: break-word;
}

.result-body :deep(p) {
	margin: 0 0 0.5em;
}

.result-body :deep(p:last-child) {
	margin-bottom: 0;
}

.result-body :deep(h1),
.result-body :deep(h2),
.result-body :deep(h3) {
	font-weight: 600;
	margin: 0.75em 0 0.375em;
}

.result-body :deep(h1) {
	font-size: 1rem;
}

.result-body :deep(h2) {
	font-size: 0.9375rem;
}

.result-body :deep(h3) {
	font-size: 0.8125rem;
}

.result-body :deep(ul) {
	list-style: disc;
	padding-left: 1.25rem;
}

.result-body :deep(ol) {
	list-style: decimal;
	padding-left: 1.25rem;
}

.result-body :deep(table) {
	border-collapse: collapse;
	font-size: 0.6875rem;
}

.result-body :deep(td),
.result-body :deep(th) {
	border: 1px solid var(--ql-border);
	padding: 0.125rem 0.375rem;
}

.no-nodes-msg {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	text-align: center;
	padding: 0.75rem 0;
	opacity: 0.7;
}
</style>
