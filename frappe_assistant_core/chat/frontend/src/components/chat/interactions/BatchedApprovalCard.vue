<template>
	<div v-if="reviewing" class="batch-review">
		<InteractionCard
			v-for="block in blocks"
			:key="block.id"
			:block="block"
			@approve="(blockId, responses) => emit('approve', blockId, responses)"
			@reject="(blockId, responses) => emit('reject', blockId, responses)"
		/>
	</div>

	<InteractionShell
		v-else
		class="batched-approval"
		:title="__('{0} changes to approve', [blocks.length])"
		:subtitle="__('FACO wants to make these changes together.')"
		icon="create"
		:decided="allDecided"
	>
		<ul class="bac-list">
			<li v-for="block in blocks" :key="block.id" class="bac-item" :data-interaction-id="block.id">
				<span class="bac-text">{{ approvalHeadline(block) }}</span>
				<span v-if="block.decision" class="bac-decision">{{ decisionLabel(block) }}</span>
			</li>
		</ul>

		<template #actions>
			<span v-if="allDecided" class="bac-status" role="status">
				{{ submitting ? __("Submitting…") : __("Decided") }}
			</span>
			<template v-else>
				<button type="button" class="bac-review" :disabled="submitting" @click="reviewing = true">
					{{ __("Review each") }}
				</button>
				<span class="bac-spacer" aria-hidden="true"></span>
				<button type="button" class="ql-btn ql-btn-reject" :disabled="submitting" @click="decideAll('reject')">
					{{ __("Reject all") }}
				</button>
				<button type="button" class="ql-btn ql-btn-approve" :disabled="submitting" @click="decideAll('approve')">
					{{ __("Approve all") }}
				</button>
			</template>
		</template>
	</InteractionShell>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import InteractionCard from "../InteractionCard.vue";
import InteractionShell from "./InteractionShell.vue";
import { approvalHeadline } from "./approvalHeadline";

const props = defineProps({
	// Waiting R2 approvals on one message (see findApprovalBatch), in the order AR asked.
	blocks: { type: Array, required: true },
	submitting: { type: Boolean, default: false },
});
const emit = defineEmits(["approve", "reject"]);

// "Review each" hands every write to its own card; there is no folding back mid-decision.
const reviewing = ref(false);

const allDecided = computed(() => props.blocks.every((b) => b.decision));

const RESPONSE = { approve: "approve", reject: "rejected" };

// Each block goes through the ordinary per-card decision, so the store still sends one resume.
function decideAll(choice) {
	for (const block of props.blocks) {
		if (block.decision) continue;
		const responses = (block.interrupts || []).map((i) => ({ interruptId: i.id, response: RESPONSE[choice] }));
		emit(choice, block.id, responses);
	}
}

function decisionLabel(block) {
	return block.decision.resolution === "rejected" ? __("Rejected") : __("Approved");
}
</script>

<style scoped>
.bac-list {
	list-style: none;
	margin: 0;
	padding: 0 16px 8px;
}

.bac-item {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 10px;
	padding: 6px 0;
	font-size: 13px;
	color: var(--ql-text);
}

.bac-item + .bac-item {
	border-top: 1px solid var(--ql-subtle);
}

.bac-text {
	min-width: 0;
	overflow-wrap: anywhere;
}

.bac-decision {
	flex: none;
	font-size: 12px;
	font-weight: 600;
	color: var(--ql-accent);
}

.bac-review {
	padding: 2px 4px;
	font-family: inherit;
	font-size: 12.5px;
	color: var(--ql-accent);
	background: none;
	border: none;
	text-decoration: underline;
	text-underline-offset: 2px;
	cursor: pointer;
}

.bac-review:disabled {
	opacity: 0.45;
	cursor: not-allowed;
}

.bac-review:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}

.bac-spacer {
	flex: 1;
}

.bac-status {
	font-size: 13px;
	color: var(--ql-text-muted);
}
</style>
