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
		<span class="resolved-label">{{ resolvedLabel }}</span>
	</div>
</template>

<script setup>
import { computed } from "vue";
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

const resolvedLabel = computed(() => {
	const status = props.block.status;
	const isApproval = props.interactionType === "approval";

	if (status === "expired") {
		return isApproval ? "Approval expired — resend to continue" : "Expired";
	}
	if (status === "resolved_elsewhere") {
		return "Resolved in another tab";
	}

	if (status === "aborted") {
		const action = props.block.action || formatToolName(props.block.tool_name);
		return isApproval ? `Stopped before: ${action}` : "Stopped by user";
	}
	if (isApproval) {
		const action = props.block.action || formatToolName(props.block.tool_name);
		if (status === "approved" || status === "trusted" || status === "resolved")
			return `Approved: ${action}`;
		return `Rejected: ${action}`;
	}
	const answer = props.block.userResponse;
	if (answer) {
		const display = Array.isArray(answer) ? answer.join(", ") : String(answer);
		return `Answered: ${display}`;
	}
	if (status === "resolved") return "Completed";
	return "Skipped";
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
	font-size: 0.75rem;
	color: var(--ql-text-secondary);
	font-style: italic;
}

/* Positive resolutions — teal check + label */
.resolved-approved .resolved-icon,
.resolved-trusted .resolved-icon,
.resolved-answered .resolved-icon,
.resolved-resolved .resolved-icon {
	color: var(--ql-accent);
}

.resolved-approved .resolved-label,
.resolved-trusted .resolved-label,
.resolved-answered .resolved-label,
.resolved-resolved .resolved-label {
	color: var(--ql-accent);
}

/* Rejected — danger treatment */
.resolved-rejected .resolved-icon,
.resolved-rejected .resolved-label {
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
	font-style: normal;
}
</style>
