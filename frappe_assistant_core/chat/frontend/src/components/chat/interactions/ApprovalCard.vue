<template>
	<div class="approval-card" :class="{ 'card-decided': hasDecision }">
		<!-- Gold-tinted header band -->
		<div class="approval-header">
			<div class="approval-icon-tile">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.8"
						d="M12 4v16m8-8H4"
					/>
				</svg>
			</div>
			<div class="approval-heading">
				<div class="approval-title">{{ message.entry.value ? messageTitle : `Approve: ${approvalTitle}` }}</div>
				<div v-if="subtitle" class="approval-subtitle">{{ subtitle }}</div>
			</div>
			<span v-if="!hasDecision" class="needs-you-pill">NEEDS YOU</span>
		</div>

		<template v-if="message.entry.value">
			<p v-if="message.failed.value" class="approval-description">{{ __("Couldn't load the preview") }}</p>
			<p v-else-if="message.blockedReason.value !== null" class="approval-description">
				{{ message.blockedReason.value }}
			</p>
			<EmailPreview v-else :preview="message.preview.value" v-bind="message.fields.value" />
		</template>

		<p v-else-if="toolDescription" class="approval-description">{{ toolDescription }}</p>

		<ApprovalDetails v-if="!message.entry.value" :block="block" />

		<div v-if="hasDecision" class="decided-banner">
			<span class="decided-label">{{ decidedLabel }}</span>
			<span v-if="batchInfo" class="decided-batch">{{ batchInfo }}</span>
		</div>

		<div v-else-if="message.blockedReason.value !== null" class="approval-actions">
			<button class="ql-btn ql-btn-reject" :disabled="submitting" @click="handleReject">
				{{ __("Dismiss") }}
			</button>
		</div>

		<template v-else>
			<label v-if="!message.failed.value && !isCustomisation" class="trust-choice">
				<input v-model="dontAskAgain" type="checkbox" :disabled="submitting || message.loading.value" />
				{{ __("Don't ask again for this tool") }}
			</label>
			<div class="approval-actions">
				<button
					v-if="!message.failed.value"
					class="ql-btn ql-btn-approve"
					:disabled="submitting || message.loading.value"
					@click="handleApprove(dontAskAgain && !isCustomisation ? 'trust' : 'approve')"
				>
					{{ message.entry.value ? __(message.entry.value.sendLabel) : "Approve" }}
				</button>
				<button class="ql-btn ql-btn-reject" :disabled="submitting" @click="handleReject">
					Reject
				</button>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import ApprovalDetails from "./ApprovalDetails.vue";
import EmailPreview from "./EmailPreview.vue";
import { useMessagePreview } from "./useMessagePreview";
import { isCustomisationRisk } from "@/utils/toolNames";
import { writeConsequence } from "./customisation";
import { formatToolName } from "./helpers";

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

// Message tools (send_email, reply_to_helpdesk_ticket) show their draft as a message.
const message = useMessagePreview(() => props.block);
const messageTitle = computed(() => message.preview.value?.title || __(message.entry.value.sendLabel));
const subtitle = computed(() =>
	message.entry.value ? message.preview.value?.context || "" : consequence.value,
);

const decidedLabel = computed(() => {
	const r = props.block.decision?.resolution;
	if (r === "approved") return "Approve";
	if (r === "trusted") return "Always allow";
	if (r === "rejected") return "Reject";
	return "Decided";
});

const approvalTitle = computed(() => {
	const map = {
		create_document: "Create Document",
		update_document: "Update Document",
		delete_document: "Delete Document",
		document_action: "Document Action",
	};
	return map[props.block.tool_name] || formatToolName(props.block.tool_name);
});

const consequence = computed(() => writeConsequence(props.block.tool_name, props.block.input));

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

function handleApprove(trustLevel) {
	const responses = (props.block.interrupts || []).map((i) => ({
		interruptId: i.id,
		response: trustLevel,
	}));
	emit("approve", props.block.id, responses);
}

function handleReject() {
	const responses = (props.block.interrupts || []).map((i) => ({
		interruptId: i.id,
		response: "rejected",
	}));
	emit("reject", props.block.id, responses);
}
</script>

<style scoped>
.approval-card {
	margin: 8px 0;
	border-radius: 12px;
	border: 1px solid var(--ql-gold-soft);
	background: var(--ql-surface);
	overflow: hidden;
}

/* Gold-tinted header band */
.approval-header {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 11px 14px;
	background: var(--ql-gold-soft);
	border-bottom: 1px solid var(--ql-gold-soft);
}

.approval-icon-tile {
	flex-shrink: 0;
	width: 30px;
	height: 30px;
	border-radius: 8px;
	background: var(--ql-gold);
	color: #fff;
	display: flex;
	align-items: center;
	justify-content: center;
}

.approval-icon-tile svg {
	width: 16px;
	height: 16px;
}

.approval-heading {
	flex: 1;
	min-width: 0;
}

.approval-title {
	font-size: 13px;
	font-weight: 600;
	color: var(--ql-text);
	line-height: 1.3;
}

.approval-subtitle {
	font-size: 11px;
	color: var(--ql-text-muted);
	margin-top: 2px;
}

.needs-you-pill {
	flex-shrink: 0;
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.02em;
	color: var(--ql-warning);
	background: var(--ql-gold-soft);
	padding: 3px 8px;
	border-radius: 20px;
}

.approval-description {
	margin: 0;
	padding: 8px 14px 0;
	font-size: 12px;
	color: var(--ql-text-secondary);
	line-height: 1.45;
}

/* Decided banner (post-click, pre-resume) */
.decided-banner {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 8px 14px 10px;
	font-size: 12px;
}

.decided-label {
	font-weight: 600;
	color: var(--ql-accent);
}

.decided-batch {
	color: var(--ql-text-muted);
	font-style: italic;
}

.card-decided {
	opacity: 0.75;
}

/* Action row — Approve filled, Reject quiet, Always-allow pushed right */
.approval-actions {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 4px 14px 12px;
}

.ql-btn {
	font-size: 12px;
	font-weight: 500;
	border-radius: 8px;
	cursor: pointer;
	transition: all 0.15s ease;
	white-space: nowrap;
}

.ql-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.ql-btn-approve {
	font-weight: 600;
	padding: 7px 16px;
	background: var(--ql-accent);
	color: #fff;
	border: none;
}

.ql-btn-approve:hover:not(:disabled) {
	background: var(--ql-accent-hover);
}

.ql-btn-reject {
	padding: 7px 14px;
	background: var(--ql-surface);
	color: var(--ql-text-secondary);
	border: 1px solid var(--ql-border);
}

.ql-btn-reject:hover:not(:disabled) {
	color: var(--ql-danger);
	border-color: var(--ql-danger);
}

.trust-choice {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 10px 14px 4px;
	font-size: 12px;
	color: var(--ql-text-secondary);
	cursor: pointer;
}

.trust-choice input {
	margin: 0;
	accent-color: var(--ql-accent);
}

.trust-choice:has(input:disabled) {
	cursor: default;
	opacity: 0.6;
}
</style>
