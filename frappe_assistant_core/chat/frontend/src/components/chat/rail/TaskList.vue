<template>
	<section v-if="tasks.length" class="task-section">
		<div class="task-head">Tasks · this turn</div>
		<ul class="task-list">
			<li
				v-for="t in rows"
				:key="t.id || t.title"
				class="task-row"
				:class="[`is-${t.displayStatus}`, { 'is-child': t.parentId }]"
				:aria-label="`${t.title} — ${t.displayStatus}${t.note ? ': ' + t.note : ''}`"
			>
				<div class="task-line">
					<span class="glyph" aria-hidden="true">{{ glyph(t.displayStatus) }}</span>
					<span class="title">{{ t.title }}</span>
					<span v-if="t.delegated" class="delegated">↳ specialist</span>
				</div>
				<p v-if="t.note" class="note" :class="{ 'is-reason': t.status === 'failed' }">
					{{ t.note }}
				</p>
			</li>
		</ul>
		<p v-if="summary" class="task-summary">{{ summary }}</p>
	</section>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	tasks: { type: Array, default: () => [] },
	// False once the turn is over. The model closes each task as it works, but
	// the final task is usually the answer itself — it goes `running`, the answer
	// streams, and nothing closes it. AR deliberately never fakes it to `done`,
	// so the client must stop presenting it as work still in flight.
	live: { type: Boolean, default: true },
});

const GLYPHS = {
	pending: "☐",
	running: "⠿",
	unfinished: "⠿",
	done: "✓",
	failed: "✗",
	skipped: "⊘",
};

function glyph(status) {
	return GLYPHS[status] || GLYPHS.pending;
}

const rows = computed(() =>
	props.tasks.map((t) => ({
		...t,
		displayStatus: !props.live && t.status === "running" ? "unfinished" : t.status,
	}))
);

// Only worth saying when the plan didn't finish cleanly — otherwise the
// checkmarks already say it.
const summary = computed(() => {
	if (props.live) return "";
	const total = props.tasks.length;
	const done = props.tasks.filter((t) => t.status === "done").length;
	if (!total || done === total) return "";
	return `Completed ${done} of ${total} step${total === 1 ? "" : "s"}`;
});
</script>

<style scoped>
.task-section {
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.task-head {
	font-size: 10px;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--ql-text-muted, #8a857c);
}
.task-list {
	display: flex;
	flex-direction: column;
	gap: 8px;
	margin: 0;
	padding: 0;
	list-style: none;
}
.task-row {
	display: flex;
	flex-direction: column;
	gap: 3px;
	font-size: 11.5px;
	line-height: 1.4;
	color: var(--ql-text, #1a1a17);
}
.task-row.is-child {
	padding-left: 18px;
}
.task-line {
	display: flex;
	align-items: baseline;
	gap: 7px;
}
.glyph {
	flex-shrink: 0;
	width: 13px;
	text-align: center;
	color: var(--ql-text-muted, #8a857c);
}
.title {
	flex: 1;
	min-width: 0;
}

.task-row.is-running .glyph {
	color: var(--ql-accent, #0f6e5c);
	display: inline-block;
	animation: task-spin 1.1s linear infinite;
}
/* Left open when the turn ended — it was in flight, it never got closed, and
   it is not running now. Static and muted, never animated. */
.task-row.is-unfinished .glyph {
	color: var(--ql-text-muted, #8a857c);
	opacity: 0.55;
}
.task-row.is-unfinished .title {
	color: var(--ql-text-muted, #8a857c);
}
.task-summary {
	margin: 2px 0 0;
	font-size: 10.5px;
	color: var(--ql-text-muted, #8a857c);
}
.task-row.is-done .glyph {
	color: var(--ql-accent, #0f6e5c);
}
.task-row.is-done .title {
	text-decoration: line-through;
	color: var(--ql-text-muted, #8a857c);
}
.task-row.is-failed .glyph,
.task-row.is-failed .title {
	color: var(--ql-danger, #b4453a);
}
.task-row.is-skipped .glyph,
.task-row.is-skipped .title {
	color: var(--ql-text-muted, #8a857c);
	opacity: 0.65;
}

.delegated {
	flex-shrink: 0;
	font-size: 10px;
	color: var(--ql-gold, #c9a227);
}

.note {
	margin: 1px 0 0;
	margin-left: 20px;
	font-size: 10.5px;
	line-height: 1.45;
	color: var(--ql-text-muted, #8a857c);
	overflow-wrap: anywhere;
}
.note.is-reason {
	padding: 5px 8px;
	border-radius: 6px;
	border-left: 2px solid var(--ql-danger, #b4453a);
	background: color-mix(in srgb, var(--ql-danger, #b4453a) 9%, transparent);
	color: var(--ql-danger, #b4453a);
	font-style: normal;
}

@keyframes task-spin {
	to {
		transform: rotate(360deg);
	}
}
@media (prefers-reduced-motion: reduce) {
	.task-row.is-running .glyph {
		animation: none;
	}
}
</style>
