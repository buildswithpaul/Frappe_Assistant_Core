<template>
	<div class="page-code-review" role="status">
		<div class="page-code-review-bar" :title="tooltip">
			<span class="page-code-review-message">
				{{ state === "first" ? __("This page has code FACO wrote.") : __("FACO changed this page's code.") }}
			</span>
			<button
				type="button"
				class="page-code-review-toggle"
				:aria-expanded="String(showing)"
				@click="showing = !showing"
			>
				{{ showing ? __("Hide changes") : __("View changes") }}
			</button>
			<button type="button" class="page-code-review-run" @click="emit('run')">
				{{ __("Run new version") }}
			</button>
		</div>
		<pre v-if="showing" class="page-code-review-diff" :aria-label="__('Code changes')"><code><span
			v-for="(line, index) in lines"
			:key="index"
			:class="['page-code-review-line', `is-${line.type}`]"
		>{{ MARKS[line.type] }} {{ line.text }}</span></code></pre>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

import { fac_page_line_diff } from "@/utils/facPageApproval";
import { __ } from "@/utils/i18n";

const props = defineProps({
	// "first" before any version of the script was approved, "changed" once FACO changed it.
	state: { type: String, required: true },
	approved: { type: String, default: "" },
	script: { type: String, default: "" },
});

const emit = defineEmits(["run"]);

const MARKS = { same: " ", removed: "-", added: "+" };
const tooltip = __("Until you run it, Download PDF and FACO's screenshots show the page without this code.");

const showing = ref(false);
const lines = computed(() => fac_page_line_diff(props.approved, props.script));
</script>

<style scoped>
.page-code-review {
	border-bottom: 1px solid var(--ql-border);
	background: var(--ql-subtle);
}
.page-code-review-bar {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 8px;
	padding: 8px 14px;
	font-size: 13px;
	color: var(--ql-text-secondary);
}
.page-code-review-message {
	flex: 1;
	min-width: 12em;
}
.page-code-review-toggle,
.page-code-review-run {
	padding: 4px 10px;
	border-radius: 6px;
	font-size: 13px;
	cursor: pointer;
}
.page-code-review-toggle {
	border: 1px solid var(--ql-border);
	background: none;
	color: var(--ql-text-secondary);
}
.page-code-review-run {
	border: none;
	background: var(--ql-accent);
	color: var(--ql-surface);
	font-weight: 600;
}
.page-code-review-diff {
	max-height: 40vh;
	margin: 0;
	padding: 8px 14px;
	overflow: auto;
	border-top: 1px solid var(--ql-border);
	background: var(--ql-surface);
	font-family: var(--ql-font-mono);
	font-size: 12px;
	line-height: 1.5;
}
.page-code-review-line {
	display: block;
	white-space: pre;
}
.page-code-review-line.is-removed {
	color: var(--ql-danger);
	text-decoration: line-through;
}
.page-code-review-line.is-added {
	color: var(--ql-success);
}
</style>
