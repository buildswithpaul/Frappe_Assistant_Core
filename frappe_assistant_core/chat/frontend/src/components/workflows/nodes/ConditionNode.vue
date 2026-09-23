<template>
	<div class="workflow-node condition-node">
		<Handle type="target" :position="Position.Left" />
		<div class="node-header">
			<div class="node-icon" style="color: var(--ql-warning)">
				<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"
					/>
				</svg>
			</div>
			<span class="node-label">{{ data.label }}</span>
			<span class="node-type-badge condition-badge">IF</span>
		</div>
		<div v-if="conditionSummary" class="node-preview">
			{{ conditionSummary }}
		</div>
		<div class="handle-labels">
			<span class="handle-label pass-label">Pass</span>
			<span class="handle-label fail-label">Fail</span>
		</div>
		<Handle type="source" :position="Position.Right" id="pass" :style="{ top: '35%' }" />
		<Handle type="source" :position="Position.Right" id="fail" :style="{ top: '75%' }" />
	</div>
</template>

<script setup>
import { computed } from "vue";
import { Handle, Position } from "@vue-flow/core";

const props = defineProps({
	data: { type: Object, required: true },
});

const conditionSummary = computed(() => {
	const cfg = props.data.config;
	if (!cfg?.condition_field) return "";
	const ops = {
		equals: "=",
		contains: "contains",
		greater_than: ">",
		less_than: "<",
		is_truthy: "is truthy",
		regex: "~",
	};
	const op = ops[cfg.condition_operator] || cfg.condition_operator || "";
	if (cfg.condition_operator === "is_truthy") return `${cfg.condition_field} ${op}`;
	return `${cfg.condition_field} ${op} ${cfg.condition_value || '""'}`;
});
</script>

<style scoped>
.workflow-node {
	background: var(--ql-surface);
	border: 2px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.625rem 0.75rem;
	min-width: 170px;
	max-width: 230px;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
	position: relative;
}

.workflow-node:hover {
	border-color: var(--ql-warning);
}

.node-header {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}

.node-icon {
	flex-shrink: 0;
	display: flex;
}

.node-label {
	flex: 1;
	font-size: 0.8125rem;
	font-weight: 600;
	color: var(--ql-text);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.node-type-badge {
	flex-shrink: 0;
	font-size: 0.625rem;
	font-weight: 700;
	padding: 0.0625rem 0.375rem;
	border-radius: 0.25rem;
}

.condition-badge {
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}

.node-preview {
	margin-top: 0.375rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	font-family: "SF Mono", Monaco, monospace;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.handle-labels {
	display: flex;
	flex-direction: column;
	position: absolute;
	right: 0.5rem;
	top: 0;
	bottom: 0;
	justify-content: space-around;
	pointer-events: none;
}

.handle-label {
	font-size: 0.5625rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.03em;
}

.pass-label {
	color: var(--ql-success);
}
.fail-label {
	color: var(--ql-danger);
}
</style>
