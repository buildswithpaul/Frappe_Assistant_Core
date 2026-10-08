<template>
	<div class="timeline-row" :class="`timeline-${status}`">
		<button class="timeline-line" @click="expanded = !expanded" :aria-expanded="expanded">
			<span class="timeline-chip" :class="`chip-${status}`">
				<svg
					v-if="status === 'running'"
					class="chip-spinner"
					viewBox="0 0 24 24"
					fill="none"
				>
					<circle
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="3"
						opacity="0.25"
					/>
					<path
						d="M12 2a10 10 0 0 1 10 10"
						stroke="currentColor"
						stroke-width="3"
						stroke-linecap="round"
					/>
				</svg>
				<svg
					v-else-if="status === 'error'"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="3"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
				<svg
					v-else-if="status === 'stopped'"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
				>
					<circle cx="12" cy="12" r="8" stroke-width="3" />
					<path stroke-linecap="round" stroke-width="3" d="M7 17L17 7" />
				</svg>
				<svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor">
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="3"
						d="M5 13l4 4L19 7"
					/>
				</svg>
			</span>
			<span class="timeline-label"
				>{{ row.labelPrefix }}<strong v-if="row.hasTarget">{{ row.target }}</strong></span
			>
			<svg
				class="timeline-chevron"
				:class="{ 'chevron-open': expanded }"
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
		</button>
		<div v-if="expanded" class="timeline-drawer">
			<!-- The row above already names the action and its status, so the
			     drawer carries only the payload — its own header would repeat
			     that line with an inert chevron beside it. -->
			<ToolCallBlock
				:block="{ ...row.block, isExpanded: true }"
				:show-header="false"
				@toggle="() => {}"
			/>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import ToolCallBlock from "../ToolCallBlock.vue";

const props = defineProps({
	row: { type: Object, required: true },
	// False once the turn is over: a tool whose result never arrived is
	// persisted as `running`, and must not keep spinning on an ended turn.
	live: { type: Boolean, default: true },
});

const status = computed(() =>
	!props.live && props.row.status === "running" ? "stopped" : props.row.status
);

const expanded = ref(false);
</script>

<style scoped>
.timeline-line {
	display: flex;
	align-items: center;
	gap: 7px;
	width: 100%;
	padding: 0;
	background: transparent;
	border: none;
	cursor: pointer;
	text-align: left;
	font-size: 11.5px;
	color: var(--ql-text-muted);
}

.timeline-line:hover {
	color: var(--ql-text-secondary);
}

.timeline-chip {
	flex-shrink: 0;
	width: 14px;
	height: 14px;
	border-radius: 50%;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	background: color-mix(in srgb, var(--ql-accent) 14%, transparent);
	color: var(--ql-accent);
}

.timeline-chip svg {
	width: 9px;
	height: 9px;
}

.chip-running {
	background: color-mix(in srgb, var(--ql-warning) 16%, transparent);
	color: var(--ql-warning);
}

.chip-stopped {
	background: color-mix(in srgb, var(--ql-text-muted) 16%, transparent);
	color: var(--ql-text-muted);
}

.chip-error {
	background: color-mix(in srgb, var(--ql-danger) 16%, transparent);
	color: var(--ql-danger);
}

.chip-spinner {
	animation: timeline-spin 1s linear infinite;
}

@keyframes timeline-spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

@media (prefers-reduced-motion: reduce) {
	.chip-spinner {
		animation: none;
	}
}

.timeline-label {
	flex: 1;
	line-height: 1.35;
}

/* The record the tool touched is the scannable part of the row (spec §3.2). */
.timeline-label strong {
	font-weight: 600;
	color: var(--ql-text);
}

.timeline-chevron {
	flex-shrink: 0;
	width: 11px;
	height: 11px;
	color: var(--ql-text-muted);
	opacity: 0.6;
	transition: transform 0.2s ease;
}

.timeline-chevron.chevron-open {
	transform: rotate(90deg);
}

.timeline-drawer {
	margin: 4px 0 2px 21px;
	border-left: 1px solid var(--ql-border);
	padding-left: 10px;
}
</style>
