<template>
	<div class="interaction-resolved" :class="`resolved-${block.status}`">
		<div class="resolved-icon">
			<svg v-if="isPositive" viewBox="0 0 24 24" fill="none" stroke="currentColor">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M5 13l4 4L19 7"
				/>
			</svg>
			<svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M6 18L18 6M6 6l12 12"
				/>
			</svg>
		</div>
		<span class="resolved-label">
			<span class="resolved-verb">{{ label.verb }}</span>
			<template v-if="label.subject">{{ " " }}<span class="resolved-subject">{{ label.subject }}</span></template>
		</span>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { isBuildPlanInteraction } from "@/stores/chat/interactionRegime";
import { __ } from "@/utils/i18n";
import { approvalHeadline } from "./approvalHeadline";
import { formatToolName } from "./helpers";

const props = defineProps({
	block: { type: Object, required: true },
	interactionType: { type: String, required: true },
});

// Neither "expired" nor "resolved_elsewhere" are positive — they're
// neutral/soft-fail terminal states. Existing array already excludes them.
const isPositive = computed(() =>
	["approved", "trusted", "answered", "resolved"].includes(props.block.status),
);

// What was decided: the verb in the outcome's colour, the action in plain text after it.
const label = computed(() => {
	const status = props.block.status;
	const isApproval = props.interactionType === "approval";
	const action = () => (props.block.input ? approvalHeadline(props.block) : props.block.action || formatToolName(props.block.tool_name));

	if (status === "expired") {
		return isApproval ? { verb: __("Approval expired"), subject: __("send again to continue") } : { verb: __("Expired") };
	}
	if (status === "resolved_elsewhere") return { verb: __("Resolved in another tab") };
	if (status === "aborted") {
		return isApproval ? { verb: __("Stopped before:"), subject: action() } : { verb: __("Stopped by user") };
	}
	if (isBuildPlanInteraction(props.interactionType)) {
		if (status === "approved") return { verb: __("Plan approved") };
		if (props.block.userResponse) return { verb: __("Changes requested") };
	}
	if (isApproval) {
		if (status === "approved" || status === "trusted" || status === "resolved") return { verb: __("Approved:"), subject: action() };
		return { verb: __("Rejected:"), subject: action() };
	}
	const answer = props.block.userResponse;
	if (answer) {
		const display = Array.isArray(answer) ? answer.join(", ") : String(answer);
		return { verb: __("Answered:"), subject: display };
	}
	if (status === "resolved") return { verb: __("Completed") };
	return { verb: __("Skipped") };
});
</script>

<style scoped>
.interaction-resolved {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.1875rem 0.25rem;
}

.resolved-icon {
	flex-shrink: 0;
	width: 0.875rem;
	height: 0.875rem;
	color: var(--ql-text-muted);
}

.resolved-icon svg {
	width: 100%;
	height: 100%;
}

.resolved-label {
	font-size: 12.5px;
	line-height: 1.4;
	color: var(--ql-text-secondary);
	min-width: 0;
	overflow-wrap: anywhere;
}

.resolved-verb {
	font-weight: 500;
}

/* The action reads as plain text; only the verb carries the outcome's colour. */
.resolved-subject {
	color: var(--ql-text-secondary);
}

/* Positive resolutions — teal check + label */
.resolved-approved .resolved-icon,
.resolved-trusted .resolved-icon,
.resolved-answered .resolved-icon,
.resolved-resolved .resolved-icon {
	color: var(--ql-accent);
}

.resolved-approved .resolved-verb,
.resolved-trusted .resolved-verb,
.resolved-answered .resolved-verb,
.resolved-resolved .resolved-verb {
	color: var(--ql-accent);
}

/* Rejected — danger treatment */
.resolved-rejected .resolved-icon,
.resolved-rejected .resolved-verb {
	color: var(--ql-danger);
}

/* Neutral terminal states — muted, non-italic for legibility */
.resolved-expired .resolved-icon,
.resolved-resolved_elsewhere .resolved-icon {
	color: var(--ql-text-muted);
}

.resolved-expired .resolved-label,
.resolved-resolved_elsewhere .resolved-label {
	color: var(--ql-text-muted);
}
</style>
