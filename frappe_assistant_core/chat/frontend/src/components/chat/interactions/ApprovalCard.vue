<template>
	<InteractionShell
		class="approval-card"
		:class="{ 'card-decided': hasDecision }"
		:title="title"
		:subtitle="subtitle"
		:icon="icon"
		:decided="hasDecision"
	>
		<template v-if="message.entry.value">
			<div v-if="message.failed.value" class="approval-description">{{ __("Couldn't load the preview") }}</div>
			<div v-else-if="message.blockedReason.value !== null" class="approval-description">
				{{ message.blockedReason.value }}
			</div>
			<EmailPreview v-else :preview="message.preview.value" v-bind="message.fields.value" />
		</template>

		<div v-else-if="toolDescription" class="approval-description">{{ toolDescription }}</div>

		<ApprovalDetails v-if="!message.entry.value" :block="block" @blocking="codeLoading = $event" />

		<template #actions>
			<div v-if="hasDecision" class="decided-banner" role="status">
				<span class="decided-label">{{ decidedLabel }}</span>
				<span v-if="batchInfo" class="decided-batch">{{ batchInfo }}</span>
			</div>

			<button
				v-else-if="message.blockedReason.value !== null"
				class="ql-btn ql-btn-reject"
				:disabled="submitting"
				@click="handleReject"
			>
				{{ __("Dismiss") }}
			</button>

			<template v-else>
				<label v-if="!message.failed.value && !isCustomisation" class="trust-choice">
					<input v-model="dontAskAgain" type="checkbox" :disabled="submitting || message.loading.value" />
					{{ trustText }}
				</label>
				<button
					v-if="!message.failed.value"
					class="ql-btn ql-btn-approve"
					:disabled="submitting || message.loading.value || codeLoading"
					:aria-busy="clicked === 'approve' && submitting ? 'true' : null"
					@click="handleApprove(dontAskAgain && !isCustomisation ? 'trust' : 'approve')"
				>
					{{ approveLabel }}
				</button>
				<button
					class="ql-btn ql-btn-reject"
					:disabled="submitting"
					:aria-busy="clicked === 'reject' && submitting ? 'true' : null"
					@click="handleReject"
				>
					{{ __("Reject") }}
				</button>
			</template>
		</template>
	</InteractionShell>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import { baseToolName, isCustomisationRisk } from "@/utils/toolNames";
import ApprovalDetails from "./ApprovalDetails.vue";
import EmailPreview from "./EmailPreview.vue";
import InteractionShell from "./InteractionShell.vue";
import { approvalHeadline, trustLabel } from "./approvalHeadline";
import { goesLiveFields, writeConsequence } from "./customisation";
import { useMessagePreview } from "./useMessagePreview";

const props = defineProps({
	block: { type: Object, required: true },
	submitting: { type: Boolean, default: false },
	batchInfo: { type: String, default: null },
});
const emit = defineEmits(["approve", "reject"]);

const hasDecision = computed(() => Boolean(props.block.decision));
// AR flags customisation writes: they are always asked about, so no "don't ask again".
const isCustomisation = computed(() => isCustomisationRisk(props.block));
// Ticked, the approve button also stops this tool asking again (AR Tool Trust "always").
const dontAskAgain = ref(false);
// True while the stored code a switch-on would run is loading; approving it unseen is the hole.
const codeLoading = ref(false);
// Which button sent the decision, so only that one shows it is working.
const clicked = ref(null);

// Message tools (send_email, reply_to_helpdesk_ticket) show their draft as a message.
const message = useMessagePreview(() => props.block);
const title = computed(() =>
	message.entry.value
		? message.preview.value?.title || __(message.entry.value.sendLabel)
		: approvalHeadline(props.block),
);
const subtitle = computed(() =>
	message.entry.value
		? message.preview.value?.context || ""
		: writeConsequence(props.block.tool_name, props.block.input),
);

const ICON_BY_TOOL = { create_document: "create", update_document: "update", delete_document: "delete" };
const icon = computed(() => {
	if (message.entry.value) return "message";
	if (goesLiveFields(props.block.tool_name, props.block.input).length) return "golive";
	return ICON_BY_TOOL[baseToolName(props.block.tool_name)] || "action";
});

const trustText = computed(() => trustLabel(props.block.tool_name));

const approveLabel = computed(() => {
	if (clicked.value === "approve" && props.submitting) return __("Approving…");
	return message.entry.value ? __(message.entry.value.sendLabel) : __("Approve");
});

const decidedLabel = computed(() => {
	const r = props.block.decision?.resolution;
	if (r === "approved") return __("Approved");
	if (r === "trusted") return __("Approved, won't ask again");
	if (r === "rejected") return __("Rejected");
	return __("Decided");
});

// First sentence of the full MCP tool description so the user sees *what
// this tool does* before approving. Falls back to null if unavailable.
const toolDescription = computed(() => {
	const d = props.block.toolDescription || props.block.tool_description;
	if (!d) return null;
	const cleaned = String(d).replace(/\s+/g, " ").trim();
	const firstStop = cleaned.search(/[.!?]\s/);
	if (firstStop > 0 && firstStop < 200) return cleaned.slice(0, firstStop + 1);
	return cleaned.length > 140 ? cleaned.slice(0, 140) + "…" : cleaned;
});

function respond(response) {
	return (props.block.interrupts || []).map((i) => ({ interruptId: i.id, response }));
}

function handleApprove(trustLevel) {
	clicked.value = "approve";
	emit("approve", props.block.id, respond(trustLevel));
}

function handleReject() {
	clicked.value = "reject";
	emit("reject", props.block.id, respond("rejected"));
}
</script>

<style scoped>
.approval-description {
	margin: 0;
	padding: 0 16px 4px;
	font-size: 13px;
	color: var(--ql-text-secondary);
	line-height: 1.5;
}

.decided-banner {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 8px;
	font-size: 13px;
}

.decided-label {
	font-weight: 600;
	color: var(--ql-accent);
}

.decided-batch {
	color: var(--ql-text-muted);
}

.trust-choice {
	flex-basis: 100%;
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 2px 0 6px;
	font-size: 12.5px;
	color: var(--ql-text-secondary);
	cursor: pointer;
}

.trust-choice input {
	margin: 0;
	width: 14px;
	height: 14px;
	accent-color: var(--ql-accent);
}

.trust-choice:has(input:disabled) {
	cursor: default;
	opacity: 0.6;
}
</style>
