<template>
	<div class="code-preview">
		<div class="code-bar">
			<span class="code-label">
				{{ label }}
				<span class="code-meta">{{ meta }}</span>
			</span>
			<button v-if="collapsible" type="button" class="code-toggle" :aria-expanded="expanded" @click="expanded = !expanded">
				{{ expanded ? __("Show less") : showAllLabel }}
			</button>
		</div>
		<!-- Collapsed still scrolls: every line of code the card asks about stays reachable. -->
		<div
			class="code-scroll"
			:class="{ 'code-clipped': collapsible && !expanded }"
			:style="collapsible && !expanded ? { maxHeight: `${maxHeight}px` } : null"
			tabindex="0"
			:aria-label="label"
		>
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
	maxHeight: { type: Number, default: 260 },
	label: { type: String, default: "" },
	// Stored code, when the card is updating it: switches to an old-vs-new line diff.
	previous: { type: String, default: null },
});

const MARKS = { same: " ", del: "-", add: "+" };
// About as much as the collapsed height shows; shorter code needs no toggle. Minified code is one
// long line that wraps, so its length counts too.
const COLLAPSE_AFTER_LINES = 14;
const COLLAPSE_AFTER_CHARS = 1400;
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

const lineCount = computed(() => (diff.value ? diff.value.length : props.code.split("\n").length));
const collapsible = computed(
	() => lineCount.value > COLLAPSE_AFTER_LINES || props.code.length > COLLAPSE_AFTER_CHARS,
);
const showAllLabel = computed(() =>
	lineCount.value > COLLAPSE_AFTER_LINES ? __("Show all {0} lines", [lineCount.value]) : __("Show all"),
);
const meta = computed(() => {
	if (diff.value) {
		const changed = diff.value.filter((row) => row.type !== "same").length;
		return changed === 1 ? __("1 line changed") : __("{0} lines changed", [changed]);
	}
	return lineCount.value === 1 ? __("1 line") : __("{0} lines", [lineCount.value]);
});
</script>

<style scoped>
.code-preview {
	grid-column: 1 / -1;
	min-width: 0;
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-md, 8px);
	background: var(--ql-subtle);
	overflow: hidden;
}

.code-bar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 6px 10px;
	font-size: 12px;
	background: var(--ql-surface);
	border-bottom: 1px solid var(--ql-border);
}

.code-label {
	font-weight: 600;
	color: var(--ql-text);
}

.code-meta {
	margin-left: 6px;
	font-weight: 400;
	color: var(--ql-text-muted);
}

.code-toggle {
	flex-shrink: 0;
	background: transparent;
	border: none;
	padding: 0;
	font: inherit;
	color: var(--ql-accent);
	cursor: pointer;
}

.code-toggle:hover {
	color: var(--ql-accent-hover);
}

.code-toggle:focus-visible,
.code-scroll:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: -2px;
}

.code-scroll {
	overflow: auto;
}

/* A soft fade says there is more below the fold. */
.code-clipped {
	mask-image: linear-gradient(to bottom, #000 calc(100% - 28px), transparent);
}

pre {
	margin: 0;
	padding: 8px 10px;
	font-family: var(--ql-font-mono);
	font-size: 11.5px;
	line-height: 1.55;
	color: var(--ql-text);
	/* Long lines wrap so nothing is cut off at the card's edge. */
	white-space: pre-wrap;
	overflow-wrap: anywhere;
}

.diff-line {
	display: block;
	min-height: 1.55em;
	padding-left: 1.5ch;
	text-indent: -1.5ch;
}

.diff-mark {
	display: inline-block;
	width: 1.5ch;
	text-indent: 0;
	color: var(--ql-text-muted);
	user-select: none;
}

.diff-add {
	background: color-mix(in srgb, var(--ql-success) 14%, transparent);
}

.diff-del {
	background: color-mix(in srgb, var(--ql-danger) 12%, transparent);
}
</style>
