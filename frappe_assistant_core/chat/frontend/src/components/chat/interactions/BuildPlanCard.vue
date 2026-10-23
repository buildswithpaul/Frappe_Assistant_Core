<template>
	<div class="plan-card" :class="{ 'plan-decided': decided }">
		<div class="plan-header">
			<div class="plan-title">{{ __("Build plan") }}</div>
			<div class="plan-count">{{ countLabel }}</div>
			<span v-if="!decided" class="needs-you-pill">{{ __("NEEDS YOU") }}</span>
		</div>

		<p v-if="plan.summary" class="plan-summary">{{ plan.summary }}</p>

		<section
			v-for="group in groups"
			:key="group.live ? 'live' : 'dormant'"
			class="plan-group"
			:class="group.live ? 'plan-group-live' : 'plan-group-dormant'"
		>
			<h4 class="plan-group-label">{{ group.live ? __("Goes live") : __("Stays dormant") }}</h4>
			<ul class="plan-changes">
				<li v-for="(change, index) in group.changes" :key="index" class="plan-change">
					<div class="change-head">
						<span class="change-action">{{ actionLabel(change.action) }}</span>
						<span class="change-doctype">{{ change.doctype }}</span>
						<span v-if="changeRecord(change)" class="change-record">{{ changeRecord(change) }}</span>
					</div>
					<p v-if="change.description" class="change-description">{{ change.description }}</p>
				</li>
			</ul>
		</section>

		<MockupFrame v-if="plan.mockupHtml" class="plan-mockup" :html="plan.mockupHtml" :title="__('Mockup')" />

		<div class="plan-actions">
			<button class="ql-btn ql-btn-approve" :disabled="locked" @click="approve">
				{{ __("Approve plan") }}
			</button>
			<button class="ql-btn ql-btn-reject" :disabled="locked" @click="emit('ask-for-changes')">
				{{ __("Ask for changes") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

import { __ } from "@/utils/i18n";
import { actionLabel, approvalResponses, changeRecord, groupChanges, planOf } from "./buildPlan";
import MockupFrame from "./mockup/MockupFrame.vue";

const props = defineProps({
	block: { type: Object, required: true },
	submitting: { type: Boolean, default: false },
});
const emit = defineEmits(["approve", "ask-for-changes"]);

const plan = computed(() => planOf(props.block));
const groups = computed(() => groupChanges(plan.value.changes));
const decided = computed(() => Boolean(props.block.decision));
const locked = computed(() => props.submitting || decided.value);

const countLabel = computed(() => {
	const n = plan.value.changes.length;
	return n === 1 ? __("1 change") : __("{0} changes", [n]);
});

function approve() {
	emit("approve", props.block.id, approvalResponses(props.block));
}
</script>

<style scoped>
.plan-card {
	margin: 8px 0;
	border-radius: 12px;
	border: 1px solid var(--ql-gold-soft);
	background: var(--ql-surface);
	overflow: hidden;
}

.plan-header {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 11px 14px;
	background: var(--ql-gold-soft);
}

.plan-title {
	font-size: 13px;
	font-weight: 600;
	color: var(--ql-text);
}

.plan-count {
	flex: 1;
	font-size: 11px;
	color: var(--ql-text-muted);
}

.needs-you-pill {
	flex-shrink: 0;
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.02em;
	color: var(--ql-warning);
	padding: 3px 8px;
	border-radius: 20px;
}

.plan-summary {
	margin: 12px 14px 4px;
	font-size: 14px;
	line-height: 1.5;
	color: var(--ql-text);
}

.plan-group {
	margin: 10px 14px 0;
}

.plan-group-label {
	margin: 0 0 6px;
	font-size: 11px;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: var(--ql-text-muted);
}

/* Live changes affect users the moment they run, so they carry the warning colour. */
.plan-group-live .plan-group-label {
	color: var(--ql-danger);
}

.plan-group-live .plan-change {
	border-left-color: var(--ql-danger);
}

.plan-changes {
	margin: 0;
	padding: 0;
	list-style: none;
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.plan-change {
	padding: 6px 10px;
	border-left: 3px solid var(--ql-border);
	background: var(--ql-bg);
}

.change-head {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	align-items: baseline;
	font-size: 13px;
}

.change-action {
	font-weight: 600;
	color: var(--ql-text);
}

.change-doctype {
	color: var(--ql-text);
}

.change-record {
	font-family: ui-monospace, "SF Mono", "Cascadia Code", monospace;
	font-size: 12px;
	color: var(--ql-text-secondary);
}

.change-description {
	margin: 2px 0 0;
	font-size: 13px;
	line-height: 1.45;
	color: var(--ql-text-secondary);
}

.plan-mockup {
	display: block;
	margin: 12px 14px 0;
	width: calc(100% - 28px);
}

.plan-actions {
	display: flex;
	gap: 8px;
	padding: 12px 14px;
}
</style>
