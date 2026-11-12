<template>
	<div class="workflow-node decision-node" :class="{ invalid: data.issues?.length }">
		<NodeIssueMarker :issues="data.issues || []" />
		<Handle type="target" :position="Position.Left" />
		<div class="node-header">
			<div class="node-icon">
				<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="ICON" />
				</svg>
			</div>
			<span class="node-label">{{ data.label }}</span>
			<span class="node-type-badge">AI</span>
		</div>
		<div class="node-preview" :title="question">
			{{ question || __("No question yet") }}
		</div>
		<!-- One source handle per choice, its id the choice text: a drawn edge
		     takes the handle id as its condition. Keyed by position so a rename
		     re-measures the handle instead of leaving a duplicate key behind. -->
		<ul class="choices">
			<li v-for="(choice, i) in choices" :key="i" class="choice" data-test="decision-choice">
				<span class="choice-label">{{ choice }}</span>
				<Handle type="source" :position="Position.Right" :id="choice" />
			</li>
		</ul>
	</div>
</template>

<script setup>
import { computed, nextTick, watch } from "vue";
import { Handle, Position, useVueFlow } from "@vue-flow/core";
import { __ } from "@/utils/i18n";
import { NODE_TYPES } from "../graphUtils";
import NodeIssueMarker from "./NodeIssueMarker.vue";

const props = defineProps({
	id: { type: String, default: "" },
	data: { type: Object, required: true },
});

const ICON = NODE_TYPES.find((t) => t.type === "decision").iconPath;

const question = computed(() => String(props.data.config?.question || "").trim());

// A blank choice has no text to label an edge with, so it gets no handle.
const choices = computed(() =>
	(Array.isArray(props.data.config?.choices) ? props.data.config.choices : [])
		.map((c) => String(c ?? "").trim())
		.filter(Boolean)
);

// Vue Flow measures a handle once, on mount. Re-measure when the choices change
// so an edge follows its choice to its new row.
const { updateNodeInternals } = useVueFlow();
watch(
	() => choices.value.join("\n"),
	() => nextTick(() => props.id && updateNodeInternals([props.id]))
);
</script>

<style scoped>
.workflow-node {
	position: relative;
	background: var(--ql-surface);
	border: 2px solid var(--ql-border);
	border-radius: 0.5rem;
	padding: 0.625rem 0.75rem;
	min-width: 170px;
	max-width: 230px;
	transition: border-color 0.15s ease;
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
	display: flex;
	flex-shrink: 0;
	color: var(--ql-warning);
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
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}
.node-preview {
	margin-top: 0.375rem;
	font-size: 0.6875rem;
	color: var(--ql-text-muted);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.choices {
	list-style: none;
	margin: 0.375rem -0.75rem 0 0;
	padding: 0;
}
/* The row runs to the node's right edge so its handle sits on the border. */
.choice {
	position: relative;
	padding: 0.125rem 0.75rem 0.125rem 0;
	text-align: right;
}
.choice-label {
	display: block;
	font-size: 0.625rem;
	font-weight: 600;
	color: var(--ql-text-secondary);
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.workflow-node.invalid {
	border-color: var(--ql-danger);
}
</style>
