<template>
	<div v-if="view" class="detail-section">
		<h3 class="section-label">{{ __("How it runs") }}</h3>
		<p v-if="view.note" class="steps-note">{{ view.note }}</p>
		<ol v-else class="stages">
			<li v-for="stage in view.stages" :key="stage.number" class="stage">
				<span class="stage-number" aria-hidden="true">{{ stage.number }}</span>
				<div class="stage-steps">
					<div v-for="step in stage.steps" :key="step.key" class="step">
						<span class="step-dot" :style="{ background: colorOf(step.type) }" aria-hidden="true" />
						<div class="step-text">
							<span class="step-label">{{ step.label }}</span>
							<span class="step-kind">{{ step.kind }}</span>
							<span v-for="branch in step.branches" :key="branch" class="step-branch">
								{{ branch }}
							</span>
						</div>
					</div>
				</div>
			</li>
		</ol>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import { NODE_TYPES } from "../graphUtils";
import { templateStages } from "./templateSteps";

const props = defineProps({ graphJson: { type: [String, Object], default: null } });

const MAX_NODES = 60;
const VUE_FLOW_TYPE = { input: "workflow-input", output: "workflow-output" };

function colorOf(type) {
	const vfType = VUE_FLOW_TYPE[type] || type;
	return NODE_TYPES.find((t) => t.type === vfType)?.color || "var(--ql-border)";
}

const view = computed(() => {
	if (!props.graphJson) return null;
	try {
		const graph = typeof props.graphJson === "string" ? JSON.parse(props.graphJson) : props.graphJson;
		const count = graph?.nodes?.length || 0;
		if (!count) return null;
		if (count > MAX_NODES) {
			return { note: __("{0} steps — open the template to see the full graph", [count]) };
		}
		return { stages: templateStages(graph) };
	} catch {
		return { note: __("This template's steps can't be previewed.") };
	}
});
</script>

<style scoped>
.detail-section {
	display: flex;
	flex-direction: column;
	gap: 0.5rem;
}
.section-label {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--ql-text-muted);
	text-transform: uppercase;
	letter-spacing: 0.04em;
	margin: 0;
}
.steps-note {
	font-size: 0.8125rem;
	color: var(--ql-text-muted);
	margin: 0;
}
.stages {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
}
.stage {
	display: flex;
	gap: 0.75rem;
	position: relative;
	padding-bottom: 0.75rem;
}
.stage:not(:last-child)::before {
	content: "";
	position: absolute;
	left: 0.6875rem;
	top: 1.5rem;
	bottom: 0;
	width: 1px;
	background: var(--ql-border);
}
.stage-number {
	flex: none;
	width: 1.375rem;
	height: 1.375rem;
	border-radius: 999px;
	border: 1px solid var(--ql-border);
	background: var(--ql-surface);
	color: var(--ql-text-muted);
	font-size: 0.6875rem;
	font-weight: 600;
	display: inline-flex;
	align-items: center;
	justify-content: center;
}
.stage-steps {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 0.375rem;
	padding-top: 0.0625rem;
}
.step {
	display: flex;
	gap: 0.5rem;
	align-items: baseline;
}
.step-dot {
	flex: none;
	width: 0.5rem;
	height: 0.5rem;
	border-radius: 2px;
	transform: translateY(-1px);
}
.step-text {
	display: flex;
	flex-direction: column;
	min-width: 0;
}
.step-label {
	font-size: 0.875rem;
	color: var(--ql-text);
	overflow-wrap: anywhere;
}
.step-kind,
.step-branch {
	font-size: 0.75rem;
	color: var(--ql-text-muted);
}
</style>
