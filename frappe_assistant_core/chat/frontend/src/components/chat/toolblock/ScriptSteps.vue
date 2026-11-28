<template>
	<ol class="script-steps">
		<li v-for="row in rows" :key="row.id" class="script-step">
			<button type="button" class="step-line" :aria-expanded="open.has(row.id)" @click="toggle(row.id)">
				<StatusChip :status="row.status" />
				<span class="step-label">{{ row.labelPrefix }}<strong v-if="row.hasTarget">{{ row.target }}</strong></span>
				<span v-if="row.meta" class="step-meta">{{ row.meta }}</span>
				<svg class="step-chevron" :class="{ 'chevron-open': open.has(row.id) }" viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
				</svg>
			</button>
			<!-- <div>, not <p>: a paragraph inside an assistant turn takes the message's body size. -->
			<div v-if="row.reason" class="step-reason">{{ row.reason }}</div>
			<div v-if="open.has(row.id)" class="step-drawer">
				<ToolSummary :block="row.block" :has-raw="false" />
			</div>
		</li>
		<li v-if="calls > rows.length" class="steps-more">{{ __("The first {0} of {1} steps.", [rows.length, calls]) }}</li>
	</ol>
</template>

<script setup>
import { computed, reactive } from "vue";
import { toolRowFrom } from "@/composables/useActivityTimeline";
import StatusChip from "../processing/StatusChip.vue";
import ToolSummary from "./ToolSummary.vue";
import { __ } from "@/utils/i18n";
import { scriptCalls, scriptSteps, stepMeta } from "./toolView";

const props = defineProps({
	// A run_script tool_call block that carries `steps`.
	block: { type: Object, required: true },
});

// Each step reads as the row of an ordinary tool call does: the same words, chip and numbers.
// A step whose tool the chat does not show as a row (an internal tool) has none here either.
const rows = computed(() =>
	scriptSteps(props.block)
		.map((step) => toolRowFrom(step))
		.filter(Boolean)
		.map((row) => ({ ...row, meta: row.status === "success" ? stepMeta(row.block) : "" })),
);
const calls = computed(() => scriptCalls(props.block));

const open = reactive(new Set());
function toggle(id) {
	if (!open.delete(id)) open.add(id);
}
</script>

<style scoped>
.script-steps {
	display: flex;
	flex-direction: column;
	gap: 5px;
	min-width: 0;
	margin: 0;
	padding: 0;
	list-style: none;
}
.script-step {
	min-width: 0;
}
.step-line {
	display: flex;
	align-items: center;
	gap: 7px;
	width: 100%;
	padding: 0;
	font-size: 12px;
	text-align: left;
	color: var(--ql-text-secondary);
	background: transparent;
	border: none;
	cursor: pointer;
}
.step-line:hover {
	color: var(--ql-text);
}
.step-line:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}
.step-label {
	flex: 1;
	min-width: 0;
	line-height: 1.35;
}
.step-label strong {
	font-weight: 600;
	color: var(--ql-text);
}
.step-meta {
	flex-shrink: 0;
	font-size: 11px;
	font-variant-numeric: tabular-nums;
	white-space: nowrap;
	color: var(--ql-text-muted);
}
.step-chevron {
	flex-shrink: 0;
	width: 11px;
	height: 11px;
	color: var(--ql-text-muted);
	opacity: 0.6;
	transition: transform 0.2s ease;
}
.step-chevron.chevron-open {
	transform: rotate(90deg);
}
.step-reason {
	margin: 2px 0 0 21px;
	font-size: 11px;
	line-height: 1.4;
	color: var(--ql-danger);
}
.steps-more {
	margin-left: 21px;
	font-size: 11px;
	color: var(--ql-text-muted);
}
.step-drawer {
	margin: 5px 0 4px 21px;
	padding-left: 10px;
	border-left: 1px solid var(--ql-border);
}
</style>
