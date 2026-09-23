<template>
	<div class="workflow-card" @click="$emit('click')">
		<div class="card-header">
			<div class="card-title-row">
				<h3 class="card-title">{{ workflow.workflow_name }}</h3>
				<span class="status-badge" :class="statusClass">{{ workflow.status }}</span>
			</div>
			<p v-if="workflow.description" class="card-description">{{ workflow.description }}</p>
		</div>

		<div class="card-stats">
			<div class="stat" v-if="workflow.total_runs > 0">
				<span class="stat-value">{{ workflow.total_runs }}</span>
				<span class="stat-label">runs</span>
			</div>
			<div class="stat" v-if="workflow.successful_runs > 0">
				<span class="stat-value stat-success">{{ workflow.successful_runs }}</span>
				<span class="stat-label">passed</span>
			</div>
			<div class="stat" v-if="workflow.failed_runs > 0">
				<span class="stat-value stat-failed">{{ workflow.failed_runs }}</span>
				<span class="stat-label">failed</span>
			</div>
		</div>

		<div class="card-footer">
			<div class="card-meta">
				<span
					v-if="workflow.schedule_enabled"
					class="schedule-indicator"
					title="Scheduled"
				>
					<svg class="meta-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
				</span>
				<span v-if="workflow.last_run_at" class="last-run">{{
					formatDate(workflow.last_run_at)
				}}</span>
				<span v-else class="last-run">No runs yet</span>
			</div>
			<button
				v-if="isAdmin"
				@click.stop="$emit('duplicate')"
				class="delete-btn"
				title="Duplicate agent"
				aria-label="Duplicate agent"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
					/>
				</svg>
			</button>
			<button
				v-if="isAdmin"
				@click.stop="$emit('delete')"
				class="delete-btn"
				title="Delete agent"
				aria-label="Delete agent"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
					/>
				</svg>
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { useUserStore } from "@/stores/userStore";
import { formatRelativeTime } from "@/composables/useFormatters";

const props = defineProps({
	workflow: { type: Object, required: true },
});

defineEmits(["click", "delete", "duplicate"]);

const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);

const statusClass = computed(() => {
	switch (props.workflow.status) {
		case "Active":
			return "status-active";
		case "Paused":
			return "status-paused";
		case "Archived":
			return "status-archived";
		default:
			return "status-draft";
	}
});

// formatDate → shared formatRelativeTime from useFormatters
const formatDate = formatRelativeTime;
</script>

<style scoped>
.workflow-card {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.75rem;
	padding: 1.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
}

.workflow-card:hover {
	border-color: var(--ql-accent);
	box-shadow: 0 2px 8px var(--ql-accent-soft);
}

.card-header {
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
}

.card-title-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
}

.card-title {
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	margin: 0;
	min-width: 0;
}

.card-description {
	font-size: 0.8125rem;
	color: var(--ql-text-secondary);
	margin: 0;
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.status-badge {
	flex-shrink: 0;
	font-size: 0.6875rem;
	font-weight: 600;
	padding: 0.125rem 0.5rem;
	border-radius: 9999px;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}

.status-draft {
	background: rgba(156, 163, 175, 0.15);
	color: var(--ql-text-muted);
}
.status-active {
	background: rgba(34, 197, 94, 0.15);
	color: var(--ql-success);
}
.status-paused {
	background: rgba(245, 158, 11, 0.15);
	color: var(--ql-warning);
}
.status-archived {
	background: rgba(239, 68, 68, 0.15);
	color: var(--ql-danger);
}

.card-stats {
	display: flex;
	gap: 1rem;
}

.stat {
	display: flex;
	align-items: baseline;
	gap: 0.25rem;
}

.stat-value {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
}

.stat-success {
	color: var(--ql-success);
}
.stat-failed {
	color: var(--ql-danger);
}

.stat-label {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.card-footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-top: auto;
}

.card-meta {
	display: flex;
	align-items: center;
	gap: 0.375rem;
}

.meta-icon {
	width: 0.875rem;
	height: 0.875rem;
	color: var(--ql-accent);
}

.schedule-indicator {
	display: flex;
	align-items: center;
}

.last-run {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}

.delete-btn {
	padding: 0.375rem;
	color: var(--ql-text-muted);
	background: transparent;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.delete-btn:hover {
	color: var(--ql-danger);
	background: rgba(239, 68, 68, 0.1);
}
</style>
