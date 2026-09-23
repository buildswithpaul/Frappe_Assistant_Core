<template>
	<div class="workflow-node input-node">
		<div class="node-header">
			<div class="node-icon" style="color: var(--ql-text-muted)">
				<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M13 9l3 3m0 0l-3 3m3-3H8m13 0a9 9 0 11-18 0 9 9 0 0118 0z"
					/>
				</svg>
			</div>
			<span class="node-label">{{ data.label }}</span>
			<span class="node-type-badge input-badge">IN</span>
		</div>
		<Handle type="source" :position="Position.Right" />
	</div>
</template>

<script setup>
import { Handle, Position } from "@vue-flow/core";

defineProps({
	data: { type: Object, required: true },
});
</script>

<style scoped>
.workflow-node {
	background: var(--ql-surface);
	border: 2px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.625rem 0.75rem;
	min-width: 160px;
	max-width: 220px;
	transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.workflow-node:hover {
	border-color: var(--ql-text-muted);
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
	text-transform: uppercase;
}

.input-badge {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}
</style>
