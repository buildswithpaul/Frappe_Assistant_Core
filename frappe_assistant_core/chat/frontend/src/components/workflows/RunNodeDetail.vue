<template>
	<div class="node-detail" :class="{ open }">
		<button class="node-row" @click.stop="open = !open">
			<span class="node-name">{{ nodeRun.node_label || nodeRun.node_id }}</span>
			<span class="status-badge" :class="statusClass(nodeRun.status)">{{
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

			<div v-if="renderedOutput" class="io-section">
				<div class="io-label">Output</div>
				<div class="io-output markdown-body" v-html="renderedOutput"></div>
				<div v-if="nodeRun.output_text_truncated" class="truncated-note">
					Output truncated for display
				</div>
			</div>

			<div v-if="nodeRun.input_text" class="io-section">
				<button class="input-toggle" @click.stop="showInput = !showInput">
					{{ showInput ? "Hide input" : "Show input" }}
				</button>
				<pre v-if="showInput" class="io-input">{{ nodeRun.input_text }}</pre>
				<div v-if="showInput && nodeRun.input_text_truncated" class="truncated-note">
					Input truncated for display
				</div>
			</div>
		</div>

		<div class="node-meta">
			<span v-if="nodeRun.duration_ms">{{ formatDuration(nodeRun.duration_ms) }}</span>
			<span v-if="nodeRun.model_id" class="meta-model">{{ nodeRun.model_id }}</span>
			<span v-if="nodeRun.credits_used" class="meta-dim"
				>{{ formatCredits(nodeRun.credits_used) }} credits</span
			>
			<span v-if="nodeRun.tool_calls_count" class="meta-dim"
				>{{ nodeRun.tool_calls_count }} tool call{{
					nodeRun.tool_calls_count > 1 ? "s" : ""
				}}</span
			>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

const props = defineProps({
	nodeRun: { type: Object, required: true },
});

const open = ref(false);
const showInput = ref(false);

const renderedOutput = computed(() => {
	if (!props.nodeRun.output_text) return "";
	return DOMPurify.sanitize(marked.parse(props.nodeRun.output_text));
});

function statusClass(status) {
	const s = status?.toLowerCase();
	if (s === "completed") return "badge-success";
	if (s === "running") return "badge-running";
	if (s === "failed") return "badge-danger";
	if (s === "cancelled") return "badge-warning";
	return "badge-queued";
}

function formatDuration(ms) {
	if (!ms) return "";
	if (ms < 1000) return `${ms}ms`;
	if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
	const m = Math.floor(ms / 60000);
	const s = Math.round((ms % 60000) / 1000);
	return `${m}m ${s}s`;
}

function formatCredits(credits) {
	if (!credits) return "";
	if (credits < 0.01) return credits.toFixed(4);
	if (credits < 1) return credits.toFixed(2);
	return credits.toFixed(1);
}

function truncate(text, len) {
	if (!text) return "";
	return text.length > len ? text.slice(0, len) + "..." : text;
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
