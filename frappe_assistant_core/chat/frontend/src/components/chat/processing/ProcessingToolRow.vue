<template>
	<div class="timeline-row" :class="`timeline-${status}`">
		<button class="timeline-line" @click="expanded = !expanded" :aria-expanded="expanded">
			<StatusChip :status="status" />
			<span class="timeline-label"
				>{{ row.labelPrefix }}<strong v-if="row.hasTarget">{{ row.target }}</strong></span
			>
			<span v-if="meta" class="timeline-meta">{{ meta }}</span>
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
		<!-- <div>, not <p>: a paragraph inside an assistant turn takes the message's body size. -->
		<div v-if="row.reason" class="timeline-reason">{{ row.reason }}</div>
		<a v-if="row.appliesTo" class="timeline-open" :href="row.appliesTo.url" target="_blank" rel="noopener">{{
			__("Open a new {0}", [row.appliesTo.doctype])
		}}</a>
		<div v-if="expanded" class="timeline-drawer">
			<!-- The row above already names the action and its status, so the
			     drawer carries only the payload. -->
			<ToolDetails :block="row.block" />
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { __ } from "@/utils/i18n";
import ToolDetails from "../toolblock/ToolDetails.vue";
import { stepMeta } from "../toolblock/toolView";
import StatusChip from "./StatusChip.vue";

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

// How much came back and how long it took, once the call has finished well.
const meta = computed(() => (status.value === "success" ? stepMeta(props.row.block) : ""));
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

.timeline-label {
	flex: 1;
	line-height: 1.35;
}

/* The record the tool touched is the scannable part of the row (spec §3.2). */
.timeline-label strong {
	font-weight: 600;
	color: var(--ql-text);
}

.timeline-meta {
	flex-shrink: 0;
	font-size: 11px;
	font-variant-numeric: tabular-nums;
	white-space: nowrap;
	color: var(--ql-text-muted);
}
.timeline-open {
	display: inline-block;
	margin: 2px 0 0 21px;
	font-size: 11px;
	color: var(--ql-accent);
	text-decoration: none;
}

.timeline-open:hover {
	text-decoration: underline;
}

.timeline-reason {
	margin: 2px 0 0 21px;
	font-size: 11px;
	line-height: 1.4;
	color: var(--ql-danger);
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
