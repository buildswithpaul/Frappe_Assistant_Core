<template>
	<div class="log-view">
		<div class="header">
			<button class="back-btn" @click="$emit('back')">← Back</button>
			<h3 class="log-title">Fire log — {{ triggerTitle || triggerName }}</h3>
		</div>

		<div v-if="loading" class="state-block">Loading…</div>
		<div v-else-if="logs.length === 0" class="empty-state">
			This trigger has not fired yet.
		</div>
		<table v-else class="log-table">
			<thead>
				<tr>
					<th>When</th>
					<th>Status</th>
					<th>Target</th>
					<th>FAC Cloud Run</th>
					<th>Message</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="row in logs" :key="row.name">
					<td class="nowrap">{{ formatDate(row.fired_at) }}</td>
					<td>
						<span class="chip" :class="statusClass(row.status)">
							{{ row.status }}
						</span>
					</td>
					<td class="mono">{{ row.reference_doctype }} / {{ row.reference_docname }}</td>
					<td class="mono">{{ row.fac_cloud_run_id || "—" }}</td>
					<td class="error">{{ row.error_message || "" }}</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import api from "@/api/client";
import { logger } from "@/utils/logger";

const props = defineProps({
	triggerName: { type: String, required: true },
	triggerTitle: { type: String, default: "" },
});

defineEmits(["back"]);

const logs = ref([]);
const loading = ref(false);

onMounted(() => refresh());
watch(
	() => props.triggerName,
	() => refresh()
);

async function refresh() {
	if (!props.triggerName) return;
	loading.value = true;
	try {
		const res = await api.workflows.triggers.log(props.triggerName, 50);
		logs.value = res?.logs || [];
	} catch (err) {
		logger.error("Failed to load trigger log", err);
		logs.value = [];
	} finally {
		loading.value = false;
	}
}

function formatDate(s) {
	if (!s) return "";
	try {
		return new Date(s).toLocaleString();
	} catch {
		return s;
	}
}

function statusClass(status) {
	switch (status) {
		case "dispatched":
			return "chip-on";
		case "quota_skipped":
			return "chip-warn";
		case "filtered_out":
			return "chip-off";
		case "ar_error":
		case "enqueue_failed":
			return "chip-error";
		default:
			return "chip-off";
	}
}
</script>

<style scoped>
.log-view {
	display: flex;
	flex-direction: column;
	gap: 0.75rem;
	color: var(--ql-text);
}
.header {
	display: flex;
	align-items: center;
	gap: 0.75rem;
}
.back-btn {
	background: none;
	border: none;
	color: var(--ql-accent);
	cursor: pointer;
	font-size: 0.8125rem;
	padding: 0;
}
.back-btn:hover {
	color: var(--ql-accent-hover);
}
.log-title {
	margin: 0;
	font-size: 0.9375rem;
	font-weight: 600;
	color: var(--ql-text);
}
.state-block,
.empty-state {
	padding: 1.5rem;
	text-align: center;
	color: var(--ql-text-secondary);
}
.log-table {
	width: 100%;
	font-size: 0.75rem;
	border-collapse: collapse;
	color: var(--ql-text);
}
.log-table th,
.log-table td {
	text-align: left;
	padding: 0.375rem 0.5rem;
	border-bottom: 1px solid var(--ql-border);
	vertical-align: top;
}
.log-table th {
	font-weight: 600;
	color: var(--ql-text-secondary);
	background: var(--ql-subtle);
}
.nowrap {
	white-space: nowrap;
}
.mono {
	font-family: "SF Mono", Monaco, monospace;
}
.error {
	color: var(--ql-danger);
	max-width: 17.5rem;
	word-break: break-word;
}
.chip {
	font-size: 0.6875rem;
	padding: 0.0625rem 0.4375rem;
	border-radius: 0.625rem;
	font-weight: 500;
}
.chip-on {
	background: color-mix(in srgb, var(--ql-success) 18%, transparent);
	color: var(--ql-success);
}
.chip-off {
	background: var(--ql-subtle);
	color: var(--ql-text-secondary);
}
.chip-warn {
	background: color-mix(in srgb, var(--ql-warning) 20%, transparent);
	color: var(--ql-warning);
}
.chip-error {
	background: color-mix(in srgb, var(--ql-danger) 18%, transparent);
	color: var(--ql-danger);
}
</style>
