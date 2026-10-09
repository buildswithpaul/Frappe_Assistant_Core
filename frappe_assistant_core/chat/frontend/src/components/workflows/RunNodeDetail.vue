<template>
	<div class="node-detail" :class="{ open }">
		<button class="node-row" @click.stop="open = !open">
			<span class="node-name">{{ nodeRun.node_label || nodeRun.node_id }}</span>
			<span class="status-badge" :class="badgeClass(nodeRun.status)">{{
				nodeRun.status
			}}</span>
			<svg
				class="chevron"
				:class="{ rotated: open }"
				width="10"
				height="10"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
			</svg>
		</button>

		<!-- Collapsed preview -->
		<div v-if="!open" class="preview">
			<div v-if="nodeRun.error_message" class="preview-error">
				{{ truncate(nodeRun.error_message, 150) }}
			</div>
			<div v-else-if="nodeRun.output_text" class="preview-output">
				{{ truncate(nodeRun.output_text, 120) }}
			</div>
		</div>

		<!-- Expanded detail -->
		<div v-if="open" class="detail-body" @click.stop>
			<div v-if="nodeRun.error_message" class="full-error">
				{{ nodeRun.error_message }}
			</div>

			<div v-if="isJsonNode && nodeRun.output_text" class="io-section">
				<div class="io-label">{{ __("Output") }}</div>
				<pre class="io-json">{{ prettyJson }}</pre>
				<div v-if="nodeRun.output_text_truncated" class="truncated-note">
					{{ __("Output truncated for display: showing the first 10,000 characters") }}
				</div>
			</div>
			<div v-else-if="renderedOutput" class="io-section">
				<div class="io-label">{{ __("Output") }}</div>
				<div class="io-output markdown-body" v-html="renderedOutput"></div>
				<div v-if="nodeRun.output_text_truncated" class="truncated-note">
					{{ __("Output truncated for display: showing the first 10,000 characters") }}
				</div>
			</div>

			<div v-if="nodeRun.input_text" class="io-section">
				<button class="input-toggle" @click.stop="showInput = !showInput">
					{{ showInput ? __("Hide input") : __("Show input") }}
				</button>
				<pre v-if="showInput" class="io-input">{{ nodeRun.input_text }}</pre>
				<div v-if="showInput && nodeRun.input_text_truncated" class="truncated-note">
					{{ __("Input truncated for display: showing the first 10,000 characters") }}
				</div>
			</div>
		</div>

		<div class="node-meta">
			<span v-if="nodeRun.duration_ms">{{ formatDuration(nodeRun.duration_ms) }}</span>
			<span v-if="nodeRun.model_id" class="meta-model">{{ nodeRun.model_id }}</span>
			<span v-if="nodeRun.credits_used" class="meta-dim"
				>{{ __("{0} credits", [formatCredits(nodeRun.credits_used)]) }}</span
			>
			<span v-if="loop">{{
				__("{0} processed · {1} failed · {2} over the limit", [
					loop.processed,
					loop.failed,
					loop.skipped,
				])
			}}</span>
			<span v-if="nodeRun.tool_calls_count" class="meta-dim"
				>{{
					nodeRun.tool_calls_count > 1
						? __("{0} tool calls", [nodeRun.tool_calls_count])
						: __("1 tool call")
				}}</span
			>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { __ } from "@/utils/i18n";
import {
	formatCredits,
	formatDuration,
	loopSummary,
	parseJsonMaybe,
	statusClass,
	truncate,
} from "./runs/runFormat";

const props = defineProps({
	nodeRun: { type: Object, required: true },
});

const open = ref(false);
const showInput = ref(false);

const renderedOutput = computed(() => {
	if (!props.nodeRun.output_text) return "";
	return DOMPurify.sanitize(marked.parse(props.nodeRun.output_text));
});

const isJsonNode = computed(() => ["tool", "loop"].includes(props.nodeRun.node_type));

const prettyJson = computed(() => {
	const v = parseJsonMaybe(props.nodeRun.output_text, null);
	return v === null ? props.nodeRun.output_text : JSON.stringify(v, null, 2);
});

const loop = computed(() =>
	props.nodeRun.node_type === "loop" ? loopSummary(props.nodeRun.output_text) : null
);

function badgeClass(status) {
	return statusClass(status) || "badge-queued";
}
</script>

<style scoped>
.node-detail {
	padding: 0.375rem 0;
	border-bottom: 1px solid var(--ql-border-subtle, var(--ql-border));
}

.node-detail:last-child {
	border-bottom: none;
}

.node-row {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	width: 100%;
	background: none;
	border: none;
	padding: 0.125rem 0;
	cursor: pointer;
	text-align: left;
}

.node-name {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text);
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.chevron {
	flex-shrink: 0;
	color: var(--ql-text-muted);
	transition: transform 0.15s;
}

.chevron.rotated {
	transform: rotate(90deg);
}

.status-badge {
	font-size: 0.625rem;
	font-weight: 600;
	padding: 0.0625rem 0.375rem;
	border-radius: 999px;
	flex-shrink: 0;
}

.badge-success {
	background: rgba(16, 185, 129, 0.12);
	color: #059669;
}

.badge-danger {
	background: rgba(239, 68, 68, 0.12);
	color: #dc2626;
}

.badge-running {
	background: rgba(59, 130, 246, 0.12);
	color: #2563eb;
}

.badge-warning {
	background: rgba(245, 158, 11, 0.12);
	color: #d97706;
}

.badge-timeout {
	background: color-mix(in srgb, var(--ql-danger) 10%, transparent);
	color: var(--ql-warning);
	border: 1px solid color-mix(in srgb, var(--ql-warning) 40%, transparent);
}

.badge-queued {
	background: rgba(107, 114, 128, 0.12);
	color: var(--ql-text-muted);
}

.preview {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	line-height: 1.4;
}

.preview-error {
	color: #dc2626;
}

.detail-body {
	margin-top: 0.375rem;
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}

.full-error {
	font-size: 0.6875rem;
	color: #dc2626;
	background: rgba(239, 68, 68, 0.08);
	border-radius: 0.25rem;
	padding: 0.375rem 0.5rem;
	white-space: pre-wrap;
	word-break: break-word;
}

.io-label {
	font-size: 0.625rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: var(--ql-text-muted);
	margin-bottom: 0.25rem;
}

.io-output {
	font-size: 0.75rem;
	line-height: 1.5;
	color: var(--ql-text);
	background: var(--ql-bg-subtle, rgba(0, 0, 0, 0.03));
	border-radius: 0.25rem;
	padding: 0.5rem 0.625rem;
	max-height: 320px;
	overflow-y: auto;
	word-break: break-word;
}

.io-output :deep(p) {
	margin: 0 0 0.5em;
}

.io-output :deep(p:last-child) {
	margin-bottom: 0;
}

.io-output :deep(table) {
	border-collapse: collapse;
	font-size: 0.6875rem;
}

.io-output :deep(td),
.io-output :deep(th) {
	border: 1px solid var(--ql-border);
	padding: 0.125rem 0.375rem;
}

.io-output :deep(code) {
	font-size: 0.6875rem;
	background: rgba(0, 0, 0, 0.06);
	padding: 0.0625rem 0.25rem;
	border-radius: 0.1875rem;
}

.io-json {
	margin: 0;
	max-height: 20rem;
	overflow: auto;
	font-family: var(--ql-font-mono);
	font-size: 0.6875rem;
	white-space: pre-wrap;
	word-break: break-word;
	background: var(--ql-subtle);
	padding: 0.5rem;
	border-radius: var(--ql-radius-sm);
}

.input-toggle {
	background: none;
	border: none;
	padding: 0;
	font-size: 0.6875rem;
	color: var(--ql-accent, #0d9488);
	cursor: pointer;
}

.input-toggle:hover {
	text-decoration: underline;
}

.io-input {
	margin: 0.25rem 0 0;
	font-size: 0.6875rem;
	line-height: 1.4;
	color: var(--ql-text-muted);
	background: var(--ql-bg-subtle, rgba(0, 0, 0, 0.03));
	border-radius: 0.25rem;
	padding: 0.5rem 0.625rem;
	max-height: 240px;
	overflow: auto;
	white-space: pre-wrap;
	word-break: break-word;
}

.truncated-note {
	font-size: 0.625rem;
	font-style: italic;
	color: var(--ql-text-muted);
	margin-top: 0.25rem;
}

.node-meta {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-top: 0.25rem;
	font-size: 0.625rem;
	color: var(--ql-text-muted);
}

.meta-model {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	max-width: 10rem;
}

.meta-dim {
	opacity: 0.8;
}
</style>
