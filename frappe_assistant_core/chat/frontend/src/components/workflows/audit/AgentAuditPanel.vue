<template>
	<aside class="audit-panel">
		<div class="panel-header">
			<span class="panel-title">Audit</span>
			<button
				@click="$emit('close')"
				class="panel-close"
				title="Close"
				aria-label="Close audit panel"
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

		<div class="panel-body">
			<AuditWindowPicker v-model="selectedWindow" />

			<div v-if="isLoading" class="audit-loading">
				<div class="mini-spinner"></div>
				<span>Loading audit data...</span>
			</div>

			<div v-else-if="error" class="audit-error">
				<p>{{ error }}</p>
				<button class="retry-btn" @click="loadAudit">Retry</button>
			</div>

			<template v-else-if="data">
				<AuditStatCards :stats="data.stats" />
				<AuditRunsChart :series="data.runs_per_day" />

				<div class="audit-footnote">
					<p>
						<strong>Avg credits</strong> reflects the agent's actual credit usage in
						the selected window. Convert to currency using your billing page —
						credit-to-currency rates can vary by plan and gateway.
					</p>
					<p>
						<strong>Acceptance rate</strong> (how often a draft was approved, edited,
						or rejected by a human) is not yet tracked. Coming in a future release.
					</p>
				</div>
			</template>
		</div>
	</aside>
</template>

<script setup>
import { ref, watch } from "vue";
import { api } from "@/api/client";
import AuditWindowPicker from "./AuditWindowPicker.vue";
import AuditStatCards from "./AuditStatCards.vue";
import AuditRunsChart from "./AuditRunsChart.vue";

const props = defineProps({
	workflowId: { type: String, required: true },
});

defineEmits(["close"]);

const selectedWindow = ref("last_7_days");
const data = ref(null);
const isLoading = ref(false);
const error = ref(null);

async function loadAudit() {
	if (!props.workflowId) return;
	isLoading.value = true;
	error.value = null;
	try {
		data.value = await api.workflows.getAuditSummary(props.workflowId, selectedWindow.value);
	} catch (err) {
		error.value = err?.message || "Failed to load audit data";
		data.value = null;
	} finally {
		isLoading.value = false;
	}
}

watch(
	() => [props.workflowId, selectedWindow.value],
	() => loadAudit(),
	{ immediate: true }
);
</script>

<style scoped>
.audit-panel {
	width: 380px;
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

.panel-body {
	flex: 1;
	overflow-y: auto;
	padding: 1rem;
	display: flex;
	flex-direction: column;
	gap: 1rem;
}

.audit-loading {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	padding: 1.5rem 0;
	color: var(--ql-text-muted);
	font-size: 0.875rem;
}

.mini-spinner {
	width: 14px;
	height: 14px;
	border: 2px solid var(--ql-border);
	border-top-color: var(--ql-accent);
	border-radius: 50%;
	animation: spin 0.8s linear infinite;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

.audit-error {
	background: rgba(239, 68, 68, 0.06);
	border: 1px solid rgba(239, 68, 68, 0.2);
	border-radius: 0.5rem;
	padding: 0.875rem;
	color: var(--ql-text);
	font-size: 0.8125rem;
}

.audit-error p {
	margin: 0 0 0.5rem;
}

.retry-btn {
	background: var(--ql-surface);
	border: 1px solid var(--ql-border);
	border-radius: 0.375rem;
	padding: 0.25rem 0.625rem;
	font-size: 0.75rem;
	cursor: pointer;
	color: var(--ql-text);
}

.audit-footnote {
	background: var(--ql-subtle);
	border-radius: 0.5rem;
	padding: 0.75rem 0.875rem;
	font-size: 0.75rem;
	color: var(--ql-text-muted);
	line-height: 1.45;
}

.audit-footnote p {
	margin: 0 0 0.5rem;
}

.audit-footnote p:last-child {
	margin-bottom: 0;
}

.audit-footnote strong {
	color: var(--ql-text);
}
</style>
