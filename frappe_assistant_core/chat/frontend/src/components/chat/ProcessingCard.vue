<template>
	<div class="processing-card" :class="{ 'processing-active': isActive }">
		<!-- Card Header — borderless, inline feel -->
		<!-- A group whose every row is filtered out has nothing to disclose, so it
		     renders as a plain status line rather than a control that opens nothing. -->
		<component
			:is="stream.length ? 'button' : 'div'"
			class="processing-card-header"
			@click="stream.length && $emit('toggle')"
			:aria-expanded="stream.length ? isExpanded : undefined"
		>
			<!-- Status Icon -->
			<div class="processing-status-icon" :class="statusIconClass">
				<!-- Spinner when active -->
				<svg v-if="isActive" viewBox="0 0 24 24" fill="none">
					<circle
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="2"
						opacity="0.25"
					/>
					<path
						d="M12 2a10 10 0 0 1 10 10"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
					/>
				</svg>
				<!-- Warning when errors -->
				<svg v-else-if="hasErrors" viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
					/>
				</svg>
				<!-- Checkmark when complete -->
				<svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M5 13l4 4L19 7"
					/>
				</svg>
			</div>

			<!-- Summary Text -->
			<span class="processing-summary">{{ summaryText }}</span>

			<!-- Chevron — omitted when there is no body to reveal -->
			<svg
				v-if="stream.length"
				class="processing-chevron"
				:class="{ 'chevron-open': isExpanded }"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M9 5l7 7-7 7"
				/>
			</svg>
		</component>

		<!-- Expanded content — one ordered pass over the turn's blocks, so the
		     rows read in the order the work actually happened. A group of only
		     internal tools renders nothing, so there is no body to open. -->
		<div v-if="isExpanded && stream.length" class="processing-card-content">
			<div class="processing-stream">
				<template v-for="entry in stream" :key="entry.key">
					<ThinkingBlock
						v-if="entry.kind === 'thinking'"
						:block="entry.block"
						@toggle="(blockId) => $emit('toggleBlock', messageIndex, blockId)"
					/>
					<InteractionCard
						v-else-if="entry.kind === 'interaction'"
						:block="entry.block"
					/>
					<ProcessingToolRow v-else-if="entry.kind === 'tool'" :row="entry.row" />
				</template>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import ThinkingBlock from "./ThinkingBlock.vue";
import InteractionCard from "./InteractionCard.vue";
import ProcessingToolRow from "./processing/ProcessingToolRow.vue";
import { toolRowFrom } from "@/composables/useActivityTimeline";
import { processingSummary } from "./processingSummary";

const props = defineProps({
	blocks: {
		type: Array,
		required: true,
	},
	isStreaming: {
		type: Boolean,
		default: false,
	},
	isExpanded: {
		type: Boolean,
		default: false,
	},
	messageIndex: {
		type: Number,
		required: true,
	},
});

defineEmits(["toggle", "toggleBlock"]);

// Derived state
const toolBlocks = computed(() => props.blocks.filter((b) => b.type === "tool_call"));
const hasErrors = computed(() => toolBlocks.value.some((b) => b.status === "error"));

// One render list in the order the blocks arrived. The array is already
// chronological, so rendering it straight through is what makes the card read
// as a sequence of work rather than a block of tools grouped by kind. Text
// never reaches here — the model's prose renders outside the card entirely.
const RENDERED_TYPES = new Set(["thinking", "interaction"]);

const stream = computed(() => {
	const entries = [];
	for (const block of props.blocks || []) {
		if (block.type === "tool_call") {
			const row = toolRowFrom(block);
			// Internal tools (get_skill, delegate, workspace_*) stay invisible.
			if (row) entries.push({ kind: "tool", key: block.id, row });
		} else if (RENDERED_TYPES.has(block.type)) {
			entries.push({ kind: block.type, key: block.id, block });
		}
	}
	return entries;
});

const isActive = computed(() => {
	if (!props.isStreaming) return false;
	return props.blocks.some(
		(b) =>
			(b.type === "thinking" && b.isStreaming) ||
			(b.type === "tool_call" && b.status === "running")
	);
});

const statusIconClass = computed(() => {
	if (isActive.value) return "status-active";
	if (hasErrors.value) return "status-error";
	return "status-complete";
});

// Smart summary generation — pure logic lives in processingSummary.js so the
// live/completed phrasing (incl. delegate activity) is unit testable.
const summaryText = computed(() => processingSummary(props.blocks, props.isStreaming));
</script>

<style scoped>
.processing-card {
	margin: 0.375rem 0;
	border-radius: 0.5rem;
	overflow: hidden;
	transition: background-color 0.2s ease;
}

.processing-card.processing-active {
	background-color: var(--ql-accent-soft);
}

/* Header — minimal, no border box feel */
.processing-card-header {
	display: flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.375rem 0.25rem;
	background: transparent;
	border: none;
	width: 100%;
	text-align: left;
	color: var(--ql-text-muted);
	font-size: 0.8125rem;
	transition: color 0.15s ease;
}

.processing-card-header:is(button) {
	cursor: pointer;
}

.processing-card-header:is(button):hover {
	color: var(--ql-text-secondary);
}

/* Status Icon */
.processing-status-icon {
	flex-shrink: 0;
	width: 0.875rem;
	height: 0.875rem;
}

.processing-status-icon svg {
	width: 100%;
	height: 100%;
}

.processing-status-icon.status-active {
	color: var(--ql-accent);
	animation: processing-spin 1s linear infinite;
}

.processing-status-icon.status-complete {
	color: var(--ql-text-muted);
}

.processing-status-icon.status-error {
	color: var(--ql-danger);
}

@keyframes processing-spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

/* Summary */
.processing-summary {
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.processing-active .processing-summary {
	color: var(--ql-text-secondary);
}

/* Chevron */
.processing-chevron {
	flex-shrink: 0;
	width: 0.75rem;
	height: 0.75rem;
	color: var(--ql-text-muted);
	transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
	opacity: 0.6;
}

.processing-chevron.chevron-open {
	transform: rotate(90deg);
}

/* Expanded content — clean, borderless */
.processing-card-content {
	padding: 0.125rem 0 0.125rem 1.25rem;
	max-height: 500px;
	overflow-y: auto;
}

/* Remove borders from nested blocks inside the card */
.processing-card-content :deep(.thinking-block),
.processing-card-content :deep(.tool-block) {
	margin: 0;
	border: none;
	border-radius: 0;
	background: transparent;
}

.processing-card-content :deep(.thinking-header) {
	padding: 0.3125rem 0.25rem;
}

/* The run itself — one rail down the left ties the thinking blocks, tool rows
   and resolved approvals of a step into a single continuous sequence. */
.processing-stream {
	border-left: 2px solid var(--ql-border);
	padding-left: 13px;
	margin: 4px 0 8px;
	display: flex;
	flex-direction: column;
	gap: 7px;
}

@media (prefers-reduced-motion: reduce) {
	.processing-status-icon.status-active {
		animation: none;
	}
}

</style>
