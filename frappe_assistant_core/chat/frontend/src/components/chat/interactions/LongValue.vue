<template>
	<span class="long-value">
		<span v-if="!open" class="value-preview">{{ previewText(value) }}</span>
		<pre v-else class="value-full" :class="{ 'value-code': code }">{{ value }}</pre>
		<button type="button" class="value-toggle" :aria-expanded="String(open)" @click="open = !open">
			{{ open ? __("Show less") : __("Show all") }}
		</button>
	</span>
</template>

<script setup>
// A value too long to show whole: its start, and a control that opens it in full.
// What isn't shown can't be approved, so nothing is cut without a way to see the rest.
import { ref } from "vue";
import { __ } from "@/utils/i18n";
import { previewText } from "./helpers";

defineProps({
	value: { type: String, required: true },
	// Code keeps its lines and a monospace font when opened.
	code: { type: Boolean, default: false },
});

const open = ref(false);
</script>

<style scoped>
.long-value {
	display: inline-flex;
	flex-direction: column;
	align-items: flex-start;
	gap: 2px;
	max-width: 100%;
}

.value-preview {
	display: block;
	white-space: normal;
	word-break: break-word;
	min-width: 24ch;
	max-width: 48ch;
}

.value-full {
	margin: 0;
	max-width: 480px;
	max-height: 320px;
	overflow: auto;
	font: inherit;
	white-space: pre-wrap;
	word-break: break-word;
}

.value-code {
	font-family: ui-monospace, "SF Mono", "Cascadia Code", monospace;
	font-size: 11px;
}

.value-toggle {
	background: transparent;
	border: none;
	padding: 0;
	font-size: 11px;
	font-weight: 400;
	color: var(--ql-accent);
	cursor: pointer;
}

.value-toggle:hover {
	color: var(--ql-accent-hover);
}
</style>
