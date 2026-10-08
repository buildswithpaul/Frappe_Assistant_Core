<template>
	<div class="workflow-node loop-node" :class="{ invalid: data.issues?.length }">
		<NodeIssueMarker :issues="data.issues || []" />
		<Handle type="target" :position="Position.Left" />
		<div class="node-header">
			<div class="node-icon">
				<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" :d="ICON" />
				</svg>
			</div>
			<span class="node-label">{{ data.label }}</span>
			<span class="node-type-badge">{{ __("EACH") }}</span>
		</div>
		<div class="node-preview">
			{{ __("Each item in {0}", [data.config?.items_path || "rows"]) }} ·
			{{ __("max {0}", [data.config?.max_items ?? 50]) }}
		</div>
		<Handle type="source" :position="Position.Right" />
	</div>
</template>

<script setup>
import { Handle, Position } from "@vue-flow/core";
import { __ } from "@/utils/i18n";
import { NODE_TYPES } from "../graphUtils";
import NodeIssueMarker from "./NodeIssueMarker.vue";

defineProps({ data: { type: Object, required: true } });
const ICON = NODE_TYPES.find((t) => t.type === "loop").iconPath;
</script>

<style scoped>
.workflow-node {
	position: relative;
	background: var(--ql-surface);
	border: 2px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.625rem 0.75rem;
	min-width: 160px;
	max-width: 220px;
	transition: border-color 0.15s ease;
}
.workflow-node:hover {
	border-color: var(--ql-accent);
}
.node-header {
	display: flex;
	align-items: center;
	gap: 0.5rem;
}
.node-icon {
	display: flex;
	flex-shrink: 0;
	color: var(--ql-text-secondary);
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
	background: var(--ql-accent-soft);
	color: var(--ql-accent);
}
.node-preview {
	margin-top: 0.375rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.mono {
	font-family: var(--ql-font-mono);
}
.node-server {
	color: var(--ql-text-secondary);
}
.workflow-node.invalid {
	border-color: var(--ql-danger);
}
</style>
