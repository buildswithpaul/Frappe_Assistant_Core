<template>
	<div
		class="run-card"
		:class="{ expanded: isExpanded, [`run-${run.status?.toLowerCase()}`]: true }"
		@click="$emit('toggle', run.name)"
	>
		<!-- Header row: status + time -->
		<div class="run-header">
			<span class="status-badge" :class="statusClass(run.status)">
				{{ run.status }}
			</span>
			<span class="run-time">{{ relativeTime(run.started_at || run.creation) }}</span>
		</div>

		<!-- Error message (for failed runs) -->
		<div v-if="run.error_message" class="run-error" :title="run.error_message">
			<svg
				width="12"
				height="12"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				class="error-icon"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 9v2m0 4h.01M12 3l9.66 16.59A1 1 0 0120.66 21H3.34a1 1 0 01-.87-1.41L12 3z"
				/>
			</svg>
			<span class="error-text">{{ truncate(run.error_message, 80) }}</span>
		</div>

		<!-- Progress bar (for running/completed/failed with partial progress) -->
		<div v-if="run.total_nodes > 0" class="run-progress">
			<div class="progress-bar">
				<div
					class="progress-fill"
					:class="progressClass"
					:style="{ width: progressPercent + '%' }"
				></div>
			</div>
			<span class="progress-label"
				>{{ run.completed_nodes || 0 }}/{{ run.total_nodes }}</span
			>
		</div>

		<!-- Meta row: duration, credits, trigger -->
		<div class="run-meta">
			<span v-if="run.duration_ms" class="meta-item">
				<svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
				{{ formatDuration(run.duration_ms) }}
			</span>
			<span v-if="run.total_credits_used" class="meta-item credit-item">
				<svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M13 10V3L4 14h7v7l9-11h-7z"
					/>
				</svg>
				{{ formatCredits(run.total_credits_used) }} credits
			</span>
			<span v-if="run.trigger_type" class="meta-item trigger-badge">
				{{ triggerLabel(run.trigger_type) }}
			</span>
		</div>

		<!-- Expanded details -->
		<div v-if="isExpanded && expandedData" class="run-details" @click.stop>
			<div class="details-divider"></div>

			<!-- Result: the final output node's text is the run's summary -->
			<div v-if="renderedResult" class="run-result">
				<div class="result-label">Result</div>
				<div class="result-body markdown-body" v-html="renderedResult"></div>
			</div>

			<!-- Error details if no nodes ran -->
			<div
				v-if="expandedData.error_message && !expandedData.node_runs?.length"
				class="detail-error-full"
			>
				{{ expandedData.error_message }}
			</div>

			<!-- Node runs -->
			<RunNodeDetail
				v-for="nr in expandedData.node_runs || []"
				:key="nr.node_id"
				:node-run="nr"
			/>

			<div v-if="!expandedData.node_runs?.length" class="no-nodes-msg">
				No nodes were executed in this run.
			</div>
		</div>

		<!-- Expand indicator -->
		<div v-if="!isExpanded" class="expand-hint">
			<svg width="10" height="10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M19 9l-7 7-7-7"
				/>
			</svg>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import RunNodeDetail from "./RunNodeDetail.vue";

const props = defineProps({
	run: { type: Object, required: true },
	isExpanded: { type: Boolean, default: false },
	expandedData: { type: Object, default: null },
});

const renderedResult = computed(() => {
	const data = props.expandedData;
	if (!data || data.status !== "Completed" || !data.output_data) return "";
	return DOMPurify.sanitize(marked.parse(data.output_data));
});

defineEmits(["toggle"]);

const progressPercent = computed(() => {
	if (!props.run.total_nodes) return 0;
	return Math.round(((props.run.completed_nodes || 0) / props.run.total_nodes) * 100);
});

const progressClass = computed(() => {
	const s = props.run.status?.toLowerCase();
	if (s === "completed") return "fill-success";
	if (s === "failed") return "fill-danger";
	if (s === "running") return "fill-active";
	return "fill-muted";
});

function statusClass(status) {
	const s = status?.toLowerCase();
	if (s === "completed") return "badge-success";
	if (s === "running") return "badge-running";
	if (s === "queued") return "badge-queued";
	if (s === "failed") return "badge-danger";
	if (s === "cancelled") return "badge-warning";
	if (s === "pending") return "badge-queued";
	if (s === "skipped") return "badge-queued";
	return "";
}

function triggerLabel(type) {
	const labels = { manual: "Manual", scheduled: "Scheduled", api: "API" };
	return labels[type] || type;
}

function relativeTime(dateStr) {
	if (!dateStr) return "";
	const diff = Date.now() - new Date(dateStr).getTime();
	const mins = Math.floor(diff / 60000);
	if (mins < 1) return "Just now";
	if (mins < 60) return `${mins}m ago`;
	const hrs = Math.floor(mins / 60);
	if (hrs < 24) return `${hrs}h ago`;
	const days = Math.floor(hrs / 24);
	return `${days}d ago`;
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
.run-card {
	padding: 0.625rem 0.875rem;
	border-bottom: 1px solid var(--ql-border);
	cursor: pointer;
	transition: background 0.15s;
}

.run-card:hover:not(.expanded) {
	background: var(--ql-subtle);
}

/* Header */
.run-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
}

.run-time {
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	flex-shrink: 0;
}

/* Status badges */
.status-badge {
	font-size: 0.5625rem;
	font-weight: 700;
	padding: 0.1rem 0.375rem;
	border-radius: 0.25rem;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	white-space: nowrap;
}

.status-badge.mini {
	font-size: 0.5rem;
	padding: 0.0625rem 0.25rem;
}

.badge-success {
	background: rgba(34, 197, 94, 0.15);
	color: #22c55e;
}
.badge-running {
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
.badge-queued {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}
.badge-danger {
	background: rgba(239, 68, 68, 0.15);
	color: #ef4444;
}
.badge-warning {
	background: rgba(245, 158, 11, 0.15);
	color: #f59e0b;
}

/* Error message */
.run-error {
	display: flex;
	align-items: flex-start;
	gap: 0.375rem;
	margin-top: 0.375rem;
	padding: 0.375rem 0.5rem;
	background: rgba(239, 68, 68, 0.06);
	border-radius: 0.25rem;
	border-left: 2px solid rgba(239, 68, 68, 0.4);
}

.error-icon {
	color: #ef4444;
	flex-shrink: 0;
	margin-top: 1px;
}

.error-text {
	font-size: 0.6875rem;
	color: #fca5a5;
	line-height: 1.4;
	word-break: break-word;
}

/* Progress bar */
.run-progress {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	margin-top: 0.375rem;
}

.progress-bar {
	flex: 1;
	height: 4px;
	background: var(--ql-border);
	border-radius: 2px;
	overflow: hidden;
}

.progress-fill {
	height: 100%;
	border-radius: 2px;
	transition: width 0.3s ease;
}

.fill-success {
	background: #22c55e;
}
.fill-danger {
	background: #ef4444;
}
.fill-active {
	background: var(--ql-accent);
	animation: pulse-bar 1.5s ease-in-out infinite;
}
.fill-muted {
	background: var(--ql-text-muted);
}

@keyframes pulse-bar {
	0%,
	100% {
		opacity: 1;
	}
	50% {
		opacity: 0.5;
	}
}

.progress-label {
	font-size: 0.625rem;
	color: var(--ql-text-muted);
	flex-shrink: 0;
	min-width: 2rem;
}

/* Meta row */
.run-meta {
	display: flex;
	flex-wrap: wrap;
	gap: 0.5rem;
	margin-top: 0.375rem;
}

.meta-item {
	display: inline-flex;
	align-items: center;
	gap: 0.2rem;
	font-size: 0.625rem;
	color: var(--ql-text-muted);
}

.meta-item svg {
	flex-shrink: 0;
	opacity: 0.6;
}

.trigger-badge {
	padding: 0 0.25rem;
	border: 1px solid var(--ql-border);
	border-radius: 0.1875rem;
	font-size: 0.5625rem;
	text-transform: capitalize;
}

/* Expand hint */
.expand-hint {
	display: flex;
	justify-content: center;
	margin-top: 0.25rem;
	color: var(--ql-text-muted);
	opacity: 0.3;
}

.run-card:hover .expand-hint {
	opacity: 0.6;
}

/* Expanded details */
.details-divider {
	height: 1px;
	background: var(--ql-border);
	margin: 0.5rem 0;
}

.detail-error-full {
	font-size: 0.75rem;
	color: #fca5a5;
	line-height: 1.4;
	padding: 0.5rem;
	background: rgba(239, 68, 68, 0.06);
	border-radius: 0.25rem;
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
	background: var(--ql-bg-subtle, rgba(0, 0, 0, 0.03));
	border-radius: 0.25rem;
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

.result-body :deep(table) {
	border-collapse: collapse;
	font-size: 0.6875rem;
}

.result-body :deep(td),
.result-body :deep(th) {
	border: 1px solid var(--ql-border);
	padding: 0.125rem 0.375rem;
}

.credit-item {
	color: #a78bfa;
}

.no-nodes-msg {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	text-align: center;
	padding: 0.75rem 0;
	opacity: 0.7;
}
</style>
