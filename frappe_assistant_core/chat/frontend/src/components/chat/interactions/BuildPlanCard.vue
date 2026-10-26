<template>
	<InteractionShell
		class="plan-card"
		:class="{ 'plan-decided': decided }"
		:title="__('Build plan')"
		:subtitle="countLabel"
		icon="plan"
		:decided="decided"
	>
		<div class="plan-body">
			<div v-if="plan.summary" class="plan-summary">{{ plan.summary }}</div>

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
						<div v-if="change.description" class="change-description">{{ change.description }}</div>
					</li>
				</ul>
			</section>

			<MockupFrame v-if="plan.mockupHtml" class="plan-mockup" :html="plan.mockupHtml" :title="__('Mockup')" />
		</div>

		<template #actions>
			<button class="ql-btn ql-btn-approve" :disabled="locked" @click="approve">
				{{ __("Approve plan") }}
			</button>
			<button class="ql-btn ql-btn-reject" :disabled="locked" @click="emit('ask-for-changes')">
				{{ __("Ask for changes") }}
			</button>
		</template>
	</InteractionShell>
</template>

<script setup>
import { computed } from "vue";

import { __ } from "@/utils/i18n";
import { actionLabel, approvalResponses, changeRecord, groupChanges, planOf } from "./buildPlan";
import InteractionShell from "./InteractionShell.vue";
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
.plan-body {
	display: flex;
	flex-direction: column;
	gap: 12px;
	padding: 0 16px 12px;
}

.plan-summary {
	margin: 0;
	font-size: 14px;
	line-height: 1.55;
	color: var(--ql-text);
}

.plan-group-label {
	margin: 0 0 6px;
	font-size: 12px;
	font-weight: 600;
	color: var(--ql-text-secondary);
}

/* Live changes affect users the moment they run, so their heading carries the warning colour. */
.plan-group-live .plan-group-label {
	color: var(--ql-danger);
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
	padding: 8px 12px;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md, 8px);
	background: var(--ql-bg);
}

.plan-group-live .plan-change {
	border-color: color-mix(in srgb, var(--ql-danger) 35%, var(--ql-border));
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
	font-size: 12.5px;
	color: var(--ql-text-secondary);
	overflow-wrap: anywhere;
}

.change-description {
	margin: 4px 0 0;
	font-size: 13px;
	line-height: 1.5;
	color: var(--ql-text-secondary);
}

.plan-mockup {
	display: block;
	width: 100%;
}
</style>
