<template>
	<figure class="page-code-review-diff" :aria-label="first ? __('Page code') : __('Code changes')">
		<figcaption class="page-code-diff-summary">{{ summary }}</figcaption>
		<div class="page-code-diff-lines">
			<template v-for="row in rows" :key="row.key">
				<button
					v-if="row.fold"
					type="button"
					class="page-code-diff-fold"
					@click="expanded.add(row.key)"
				>
					{{ __("Show {0} unchanged lines", [row.count]) }}
				</button>
				<div v-else :class="['page-code-review-line', `is-${first ? 'same' : row.type}`]">
					<span class="page-code-diff-mark" aria-hidden="true">{{ first ? "" : MARKS[row.type] }}</span>
					<span class="page-code-diff-text">{{ row.text || " " }}</span>
				</div>
			</template>
		</div>
	</figure>
</template>

<script setup>
import { computed, reactive } from "vue";

import { fac_page_line_diff } from "@/utils/facPageApproval";
import { __ } from "@/utils/i18n";

const props = defineProps({
	// "" before any version was approved: the whole script is shown as code, not as a change.
	approved: { type: String, default: "" },
	script: { type: String, default: "" },
	first: { type: Boolean, default: false },
});

const MARKS = { same: "", removed: "−", added: "+" };
// Unchanged lines kept on each side of a change; a longer unchanged run folds away.
const CONTEXT = 3;

const expanded = reactive(new Set());
const lines = computed(() => fac_page_line_diff(props.approved, props.script));

const lineCount = (count) => (count === 1 ? __("1 line") : __("{0} lines", [count]));

const summary = computed(() => {
	if (props.first) return __("{0} of code", [lineCount(lines.value.length)]);
	const added = lines.value.filter((line) => line.type === "added").length;
	const removed = lines.value.filter((line) => line.type === "removed").length;
	return __("{0} added, {1} removed", [lineCount(added), lineCount(removed)]);
});

/** The lines to draw, with each long unchanged run between changes folded into one row. */
const rows = computed(() => {
	const all = lines.value.map((line, index) => ({ ...line, key: `l${index}` }));
	if (props.first) return all;
	const changed = all.map((line, index) => (line.type === "same" ? -1 : index)).filter((index) => index >= 0);
	const near = (index) => changed.some((at) => Math.abs(at - index) <= CONTEXT);
	const out = [];
	let run = [];
	const flush = () => {
		const key = `f${run[0]?.key}`;
		if (run.length > 1 && !expanded.has(key)) out.push({ fold: true, key, count: run.length });
		else out.push(...run);
		run = [];
	};
	for (const [index, line] of all.entries()) {
		if (line.type === "same" && !near(index)) run.push(line);
		else {
			if (run.length) flush();
			out.push(line);
		}
	}
	if (run.length) flush();
	return out;
});
</script>

<style scoped>
.page-code-review-diff {
	margin: 0 14px 12px;
	overflow: hidden;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md);
	background: var(--ql-surface);
}
.page-code-diff-summary {
	padding: 6px 12px;
	border-bottom: 1px solid var(--ql-border);
	font-size: 12px;
	font-variant-numeric: tabular-nums;
	color: var(--ql-text-muted);
}
/* The diff scrolls inside its own frame, and long lines wrap, so it never pushes the panel wide. */
.page-code-diff-lines {
	max-height: min(45vh, 420px);
	overflow-y: auto;
	padding: 4px 0;
	font-family: var(--ql-font-mono);
	font-size: 12px;
	line-height: 1.55;
	color: var(--ql-text-secondary);
}
.page-code-review-line {
	display: grid;
	grid-template-columns: 22px 1fr;
	padding-right: 12px;
}
.page-code-diff-mark {
	text-align: center;
	color: var(--ql-text-muted);
	user-select: none;
}
.page-code-diff-text {
	min-width: 0;
	white-space: pre-wrap;
	overflow-wrap: anywhere;
}
.page-code-review-line.is-added {
	background: color-mix(in srgb, var(--ql-success) 12%, transparent);
	color: var(--ql-text);
}
.page-code-review-line.is-added .page-code-diff-mark {
	color: var(--ql-success);
}
.page-code-review-line.is-removed {
	background: color-mix(in srgb, var(--ql-danger) 10%, transparent);
	color: var(--ql-text);
}
.page-code-review-line.is-removed .page-code-diff-mark {
	color: var(--ql-danger);
}
.page-code-diff-fold {
	display: block;
	width: 100%;
	margin: 2px 0;
	padding: 3px 12px 3px 22px;
	border: none;
	background: var(--ql-subtle);
	color: var(--ql-text-muted);
	font-family: var(--ql-font-ui);
	font-size: 12px;
	text-align: left;
	cursor: pointer;
}
.page-code-diff-fold:hover {
	color: var(--ql-text);
}
.page-code-diff-fold:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: -2px;
}
</style>
