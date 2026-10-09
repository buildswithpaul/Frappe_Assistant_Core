<template>
	<div
		class="run-card"
		:class="{ expanded: isExpanded, [`run-${run.status?.toLowerCase()}`]: true }"
		@click="$emit('toggle', run.name)"
	>
		<!-- Header row: status + time -->
		<div class="run-header">
			<span class="status-badge" :class="badge.cls">{{ badge.text }}</span>
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
				{{ __("{0} credits", [formatCredits(run.total_credits_used)]) }}
			</span>
			<span v-if="run.trigger_type" class="meta-item trigger-badge">
				{{ triggerLabel(run.trigger_type) }}
			</span>
		</div>

		<RunCardDetails v-if="isExpanded && expandedData" :run="expandedData" @click.stop />

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
import { __ } from "@/utils/i18n";
import RunCardDetails from "./runs/RunCardDetails.vue";
import {
	formatCredits,
	formatDuration,
	relativeTime,
	runBadge,
	triggerLabel,
	truncate,
} from "./runs/runFormat";

const props = defineProps({
	run: { type: Object, required: true },
	isExpanded: { type: Boolean, default: false },
	expandedData: { type: Object, default: null },
});

defineEmits(["toggle"]);

const badge = computed(() =>
	runBadge(
		props.run.status === props.expandedData?.status
			? { ...props.run, ...props.expandedData }
			: props.run
	)
);

const progressPercent = computed(() => {
	if (!props.run.total_nodes) return 0;
	return Math.round(((props.run.completed_nodes || 0) / props.run.total_nodes) * 100);
});

const progressClass = computed(() => {
	const s = props.run.status?.toLowerCase();
	if (s === "completed") return "fill-success";
	if (s === "failed" || s === "timed out") return "fill-danger";
	if (s === "running") return "fill-active";
	return "fill-muted";
});
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
	background: color-mix(in srgb, var(--ql-success) 15%, transparent);
	color: var(--ql-success);
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
	background: color-mix(in srgb, var(--ql-danger) 15%, transparent);
	color: var(--ql-danger);
}
.badge-warning {
	background: color-mix(in srgb, var(--ql-warning) 16%, transparent);
	color: var(--ql-warning);
}
.badge-timeout {
	background: color-mix(in srgb, var(--ql-danger) 10%, transparent);
	color: var(--ql-warning);
	border: 1px solid color-mix(in srgb, var(--ql-warning) 40%, transparent);
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

.credit-item {
	color: #a78bfa;
}
</style>
