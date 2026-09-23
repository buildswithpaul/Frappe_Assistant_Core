<template>
	<div :data-interaction-id="block.id">
		<ResolvedIndicator
			v-if="isResolved"
			:block="block"
			:interaction-type="interactionType"
		/>
		<ApprovalCard
			v-else-if="isApproval"
			:block="block"
			:submitting="isSubmittingInterrupts"
			:batch-info="batchInfo"
			@approve="(blockId, responses) => emit('approve', blockId, responses)"
			@reject="(blockId, responses) => emit('reject', blockId, responses)"
		/>
		<QuestionCard
			v-else
			:block="block"
			:interaction-type="interactionType"
			:submitting="isSubmittingInterrupts"
			@respond="handleRespond"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { useChatStore } from "@/stores/chatStore";
import { isApprovalInteraction } from "@/stores/chat/interactionRegime";
import { findActiveMessage } from "@/stores/chat/utils";
import ApprovalCard from "./interactions/ApprovalCard.vue";
import QuestionCard from "./interactions/QuestionCard.vue";
import ResolvedIndicator from "./interactions/ResolvedIndicator.vue";

const props = defineProps({
	block: { type: Object, required: true },
});

const emit = defineEmits(["approve", "reject"]);

const chatStore = useChatStore();

const interactionType = computed(() => props.block.interactionType || "approval");
const isApproval = computed(() => isApprovalInteraction(props.block.interactionType));

// Any non-pending status hides the live action buttons. `aborted` is added
// by the Stop flow when cancellation lands while the agent is paused on
// this approval — without that branch we'd render Approve/Reject on reload
// and the click would hit AR with a stale interrupt id.
const isResolved = computed(() => props.block.status !== "pending");

const isSubmittingInterrupts = computed(() => chatStore.isSubmittingInterrupts);

// "Waiting for 2 more decisions" — shown after a click while other parallel
// approval cards on this turn still need a decision. Computed against the
// live store so the banner updates as the user works through cards.
const batchInfo = computed(() => {
	if (chatStore.isSubmittingInterrupts) return "Submitting…";
	const lastMsg = findActiveMessage(chatStore.messages);
	if (!lastMsg || !lastMsg.blocks) return null;
	const pendingNoDecision = lastMsg.blocks.filter(
		(b) => b.type === "interaction" && b.status === "pending" && !b.decision,
	).length;
	if (pendingNoDecision === 0) return null;
	return pendingNoDecision === 1
		? "Waiting for 1 more decision"
		: `Waiting for ${pendingNoDecision} more decisions`;
});

function handleRespond(answer) {
	const responses = (props.block.interrupts || []).map((i) => ({
		interruptId: i.id,
		response: answer,
	}));
	emit("approve", props.block.id, responses);
}
</script>
