<template>
	<div class="workflow-node output-node">
		<Handle type="target" :position="Position.Left" />
		<div class="node-header">
			<div class="node-icon" style="color: var(--ql-text-muted)">
				<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9"
					/>
				</svg>
			</div>
			<span class="node-label">{{ data.label }}</span>
			<span class="node-type-badge output-badge">OUT</span>
		</div>
		<div v-if="data.config?.output_template" class="node-preview">
			{{ truncate(data.config.output_template, 40) }}
		</div>
	</div>
</template>

<script setup>
import { Handle, Position } from "@vue-flow/core";

defineProps({
	data: { type: Object, required: true },
});

function truncate(text, len) {
	if (!text) return "";
	return text.length > len ? text.slice(0, len) + "..." : text;
}
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
}

.output-badge {
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
}

.node-preview {
	margin-top: 0.375rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
</style>
