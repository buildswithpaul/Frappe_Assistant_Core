<template>
	<div class="code-preview">
		<div class="code-bar">
			<span class="code-label">{{ label }}</span>
			<button type="button" class="code-toggle" @click="expanded = !expanded">
				{{ expanded ? __("Collapse") : __("Expand") }}
			</button>
		</div>
		<div class="code-scroll" :style="expanded ? null : { maxHeight: `${maxHeight}px` }">
			<pre v-if="!diffRows"><code v-html="highlighted"></code></pre>
			<pre v-else><code><span v-for="(row, i) in diffRows" :key="i" class="diff-line" :class="`diff-${row.type}`"><span class="diff-mark">{{ MARKS[row.type] }}</span><span v-html="row.html"></span></span></code></pre>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { __ } from "@/utils/i18n";
import { ensureHljs, highlightCode } from "@/utils/markdown";
import { lineDiff } from "./lineDiff";

const props = defineProps({
	code: { type: String, required: true },
	language: { type: String, default: "" },
	maxHeight: { type: Number, default: 320 },
	label: { type: String, default: "" },
	// Stored code, when the card is updating it: switches to an old-vs-new line diff.
	previous: { type: String, default: null },
});

const MARKS = { same: " ", del: "-", add: "+" };
const expanded = ref(false);
// highlight.js loads lazily; bumping this re-runs the highlighting once it is in.
const hljsReady = ref(false);
onMounted(() => ensureHljs().then(() => (hljsReady.value = true)));

const highlightLanguage = computed(() => (hljsReady.value ? props.language : ""));
const highlighted = computed(() => highlightCode(props.code, highlightLanguage.value));
// Null shows the new code alone: no previous code, or too large to diff.
const diff = computed(() => (props.previous === null ? null : lineDiff(props.previous, props.code)));
const diffRows = computed(
	() => diff.value && diff.value.map((row) => ({ ...row, html: highlightCode(row.text, highlightLanguage.value) })),
);
</script>

<style scoped>
.code-preview {
	grid-column: 1 / -1;
	min-width: 0;
	border: 1px solid var(--ql-border);
	border-radius: 8px;
	overflow: hidden;
}

.code-bar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 4px 10px;
	font-size: 11px;
	background: var(--ql-surface);
	border-bottom: 1px solid var(--ql-border);
}

.code-label {
	color: var(--ql-text-muted);
}

.code-toggle {
	background: transparent;
	border: none;
	padding: 0;
	font-size: 11px;
	color: var(--ql-accent);
	cursor: pointer;
}

.code-scroll {
	overflow: auto;
}

pre {
	margin: 0;
	padding: 8px 10px;
	font-family: ui-monospace, "SF Mono", "Cascadia Code", monospace;
	font-size: 11px;
	line-height: 1.5;
	white-space: pre;
	width: max-content;
	min-width: 100%;
	box-sizing: border-box;
}

.diff-line {
	display: block;
	min-height: 1.5em;
}

.diff-mark {
	display: inline-block;
	width: 1.5ch;
	color: var(--ql-text-muted);
	user-select: none;
}

.diff-add {
	background: rgba(46, 160, 67, 0.15);
}

.diff-del {
	background: rgba(248, 81, 73, 0.15);
}
</style>
