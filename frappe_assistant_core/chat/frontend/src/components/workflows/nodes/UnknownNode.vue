<template>
	<div class="workflow-node unknown-node" :class="{ invalid: data.issues?.length }">
		<NodeIssueMarker :issues="data.issues || []" />
		<Handle type="target" :position="Position.Left" />
		<div class="node-header">
			<span class="node-label">{{ data.label }}</span>
			<span class="node-type-badge">{{ type }}</span>
		</div>
		<div class="node-preview">{{ __("Not editable in this version") }}</div>
		<Handle type="source" :position="Position.Right" />
	</div>
</template>

<script setup>
import { Handle, Position } from "@vue-flow/core";
import { __ } from "@/utils/i18n";
import NodeIssueMarker from "./NodeIssueMarker.vue";

// Registered as Vue Flow's "default" type, which it renders for any node type
// it has no component for: a graph saved by a newer builder still draws, and
// its config round-trips untouched.
defineProps({
	type: { type: String, default: "" },
	data: { type: Object, required: true },
});
</script>

<style scoped>
.workflow-node {
	position: relative;
	background: var(--ql-surface);
	border: 2px dashed var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.625rem 0.75rem;
	min-width: 160px;
	max-width: 220px;
}
.node-header {
	display: flex;
	align-items: center;
	gap: 0.5rem;
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
	max-width: 6rem;
	font-size: 0.625rem;
	font-weight: 700;
	padding: 0.0625rem 0.375rem;
	border-radius: 0.25rem;
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.node-preview {
	margin-top: 0.375rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
}
.workflow-node.invalid {
	border-color: var(--ql-danger);
}
</style>
