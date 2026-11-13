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
		class="go-live-card"
		:title="__('{0} changes go live', [blocks.length])"
		:subtitle="__('Approving switches these on for the people they reach. Each one\'s code is one click away.')"
		icon="golive"
		:decided="allDecided"
	>
		<ul class="glc-list">
			<li v-for="block in blocks" :key="block.id" class="glc-item" :data-interaction-id="block.id">
				<div class="glc-row">
					<span class="glc-text">{{ approvalHeadline(block) }}</span>
					<span v-if="block.decision" class="glc-decision">{{ decisionLabel(block) }}</span>
					<button
						type="button"
						class="glc-toggle"
						:aria-expanded="isOpen(block.id)"
						@click="toggle(block.id)"
					>
						{{ isOpen(block.id) ? __("Hide code") : __("Show code") }}
					</button>
				</div>
				<div v-if="isOpen(block.id)" class="glc-code">
					<InteractionCard :block="block" />
				</div>
			</li>
		</ul>

		<template #actions>
			<span v-if="allDecided" class="glc-status" role="status">
				{{ submitting ? __("Submitting…") : __("Decided") }}
			</span>
			<template v-else>
				<button type="button" class="glc-review" :disabled="submitting" @click="reviewing = true">
					{{ __("Review each") }}
				</button>
				<span class="glc-spacer" aria-hidden="true"></span>
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
	// Waiting switch-on approvals on one message (see findGoLiveBatch), in the order AR asked.
	blocks: { type: Array, required: true },
	submitting: { type: Boolean, default: false },
});
const emit = defineEmits(["approve", "reject"]);

// "Review each" hands every change to its own card; there is no folding back mid-decision.
const reviewing = ref(false);
const openIds = ref(new Set());

const allDecided = computed(() => props.blocks.every((b) => b.decision));

const RESPONSE = { approve: "approve", reject: "rejected" };

function isOpen(id) {
	return openIds.value.has(id);
}

function toggle(id) {
	const next = new Set(openIds.value);
	if (!next.delete(id)) next.add(id);
	openIds.value = next;
}

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
.glc-list {
	list-style: none;
	margin: 0;
	padding: 0 16px 8px;
}

.glc-item {
	padding: 6px 0;
	font-size: 13px;
	color: var(--ql-text);
}

.glc-item + .glc-item {
	border-top: 1px solid var(--ql-border);
}

.glc-row {
	display: flex;
	align-items: baseline;
	gap: 10px;
}

.glc-text {
	flex: 1;
	min-width: 0;
	overflow-wrap: anywhere;
}

.glc-decision {
	flex: none;
	font-size: 12px;
	font-weight: 600;
	color: var(--ql-accent);
}

.glc-code {
	margin-top: 6px;
}

.glc-toggle,
.glc-review {
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

.glc-toggle {
	flex: none;
}

.glc-review:disabled {
	opacity: 0.45;
	cursor: not-allowed;
}

.glc-toggle:focus-visible,
.glc-review:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}

.glc-spacer {
	flex: 1;
}

.glc-status {
	font-size: 13px;
	color: var(--ql-text-muted);
}
</style>
