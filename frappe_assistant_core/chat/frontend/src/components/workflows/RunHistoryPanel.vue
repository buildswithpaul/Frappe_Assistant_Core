<template>
	<aside class="runs-panel">
		<div class="panel-header">
			<span class="panel-title">Run History</span>
			<button
				@click="$emit('close')"
				class="panel-close"
				title="Close"
				aria-label="Close run history"
			>
				<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
			</button>
		</div>

		<!-- Runs list -->
		<div class="runs-list">
			<div v-if="isLoadingRuns && runs.length === 0" class="runs-loading">
				<div class="mini-spinner"></div>
				<span>Loading runs...</span>
			</div>

			<div v-else-if="runs.length === 0" class="runs-empty">
				<p>No runs yet. Click "Run" to execute this agent.</p>
			</div>

			<template v-else>
				<div v-for="run in runs" :key="run.name">
					<!-- Cancel button for active runs -->
					<div
						v-if="isActiveRun(run.name) && ['Queued', 'Running'].includes(run.status)"
						class="cancel-bar"
					>
						<div class="active-indicator">
							<div class="live-dot"></div>
							<span>Live</span>
						</div>
						<button
							@click.stop="handleCancel"
							class="cancel-btn"
							aria-label="Cancel run"
							:disabled="isCancelling"
						>
							{{ isCancelling ? "Cancelling..." : "Cancel" }}
						</button>
					</div>

					<RunCard
						:run="run"
						:is-expanded="expandedRun === run.name"
						:expanded-data="expandedRun === run.name ? expandedRunData : null"
						:class="{ 'run-active': isActiveRun(run.name) }"
						@toggle="toggleRun(runs.find((r) => r.name === $event))"
					/>
				</div>
			</template>
		</div>

		<!-- Load more -->
		<button
			v-if="runs.length < runsTotal"
			@click="loadMore"
			class="load-more-btn"
			:disabled="isLoadingRuns"
		>
			Load more
		</button>
	</aside>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";
import { storeToRefs } from "pinia";
import { useWorkflowStore } from "@/stores/workflowStore";
import RunCard from "./RunCard.vue";

const props = defineProps({
	/** AR Workflow docname — list_runs filters its `workflow` link on this,
	    despite the endpoint calling the argument workflow_name. */
	workflowId: { type: String, required: true },
});

defineEmits(["close"]);

const workflowStore = useWorkflowStore();
const { runs, runsTotal, isRunning, isCancelling, activeRunName, currentRun } =
	storeToRefs(workflowStore);

const isLoadingRuns = ref(false);
const expandedRun = ref(null);
const expandedRunData = ref(null);
const currentPage = ref(0);

// The poller lives in the store — its lifetime is the run's, not this panel's.
// This component only reflects what the store has polled.
onMounted(loadRuns);

watch(activeRunName, async (newName, oldName) => {
	if (newName) {
		await loadRuns();
		expandedRun.value = newName;
	} else if (oldName) {
		loadRuns();
	}
});

// Fold each polled snapshot into the list row and the expanded card.
watch(currentRun, (run) => {
	if (!run?.name) return;
	if (expandedRun.value === run.name) expandedRunData.value = run;
	const idx = runs.value.findIndex((r) => r.name === run.name);
	if (idx >= 0) runs.value.splice(idx, 1, { ...runs.value[idx], ...run });
	else if (run.name === activeRunName.value) runs.value.unshift(run);
});

function isActiveRun(runName) {
	return activeRunName.value === runName && isRunning.value;
}

async function loadRuns() {
	isLoadingRuns.value = true;
	try {
		await workflowStore.loadRuns(props.workflowId, null, 0);
		currentPage.value = 0;
	} finally {
		isLoadingRuns.value = false;
	}
}

async function loadMore() {
	isLoadingRuns.value = true;
	try {
		currentPage.value++;
		const result = await workflowStore.loadRuns(props.workflowId, null, currentPage.value);
		if (result.runs?.length) {
			const existing = new Set(runs.value.map((r) => r.name));
			const newRuns = result.runs.filter((r) => !existing.has(r.name));
			runs.value = [...runs.value, ...newRuns];
		}
	} finally {
		isLoadingRuns.value = false;
	}
}

async function toggleRun(run) {
	if (expandedRun.value === run.name) {
		expandedRun.value = null;
		expandedRunData.value = null;
		return;
	}
	expandedRun.value = run.name;
	try {
		expandedRunData.value = await workflowStore.loadRun(run.name);
	} catch {
		expandedRunData.value = null;
	}
}

async function handleCancel() {
	if (!activeRunName.value) return;
	// Cancellation is cooperative: the store keeps polling until the run
	// reports a terminal status, and credits already spent stay spent.
	await workflowStore.cancelRun(activeRunName.value).catch(() => {});
}
</script>

<style scoped>
.runs-panel {
	width: 320px;
	background: var(--ql-surface);
	border-left: 1px solid var(--ql-border);
	flex-shrink: 0;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}

.panel-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.75rem 1rem;
	border-bottom: 1px solid var(--ql-border);
	flex-shrink: 0;
}

.panel-title {
	font-size: 0.875rem;
	font-weight: 600;
	color: var(--ql-text);
}

.panel-close {
	background: transparent;
	border: none;
	color: var(--ql-text-muted);
	cursor: pointer;
	padding: 0.25rem;
	border-radius: 0.25rem;
	display: flex;
}

.panel-close:hover {
	background: var(--ql-subtle);
	color: var(--ql-text);
}

/* Cancel bar above active run */
.cancel-bar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 0.375rem 0.875rem;
	background: var(--ql-accent-soft);
	border-bottom: 1px solid var(--ql-accent-soft);
}

.active-indicator {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	font-size: 0.6875rem;
	font-weight: 600;
	color: var(--ql-accent);
}

.live-dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: var(--ql-accent);
	animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
	0%,
	100% {
		opacity: 1;
		transform: scale(1);
	}
	50% {
		opacity: 0.4;
		transform: scale(0.8);
	}
}

.cancel-btn {
	font-size: 0.6875rem;
	padding: 0.125rem 0.5rem;
	color: var(--ql-danger);
	background: transparent;
	border: 1px solid var(--ql-danger);
	border-radius: 0.25rem;
	cursor: pointer;
}

.cancel-btn:hover {
	background: rgba(239, 68, 68, 0.08);
}
.cancel-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

/* Active run highlight */
:deep(.run-active) {
	border-left: 2px solid var(--ql-accent);
}

/* Runs list */
.runs-list {
	flex: 1;
	overflow-y: auto;
}

.runs-loading,
.runs-empty {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.5rem;
	padding: 2rem 1rem;
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	text-align: center;
}

.runs-empty p {
	margin: 0;
}

.mini-spinner {
	width: 12px;
	height: 12px;
	border: 1.5px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* Load more */
.load-more-btn {
	width: 100%;
	padding: 0.5rem;
	font-size: 0.75rem;
	color: var(--ql-accent);
	background: transparent;
	border: none;
	border-top: 1px solid var(--ql-border);
	cursor: pointer;
	flex-shrink: 0;
}

.load-more-btn:hover {
	background: var(--ql-subtle);
}
.load-more-btn:disabled {
	color: var(--ql-text-muted);
	cursor: not-allowed;
}
</style>
