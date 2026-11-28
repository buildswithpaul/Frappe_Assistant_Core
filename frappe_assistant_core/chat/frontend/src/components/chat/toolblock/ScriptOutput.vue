<template>
	<div class="script-output">
		<div v-if="truncated" class="output-plain">{{ __("The script printed too much to show while the chat is live. Reload the page to see it.") }}</div>
		<div v-else-if="!text" class="output-plain">{{ running ? __("Nothing printed yet.") : __("The script printed nothing.") }}</div>
		<template v-else-if="sections">
			<template v-for="(section, i) in sections" :key="i">
				<span v-if="section.title" class="output-title">{{ section.title }}</span>
				<RecordTable v-if="section.table" :view="section.table" />
				<FieldList v-else-if="section.fields" :fields="section.fields" />
				<CodePreview v-else :code="section.json" :language="languageFor(section.json, 'json')" :label="__('Printed')" copyable />
			</template>
		</template>
		<pre v-else class="output-text" :class="{ 'output-error': failed }">{{ text }}</pre>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import { toolFailed } from "@/utils/toolResult";
import CodePreview from "../interactions/CodePreview.vue";
import FieldList from "./FieldList.vue";
import RecordTable from "./RecordTable.vue";
import { isTruncated, languageFor, printedSections, printedValues, scriptOutput } from "./toolView";

const props = defineProps({
	block: { type: Object, required: true },
});

const truncated = computed(() => isTruncated(props.block));
const text = computed(() => scriptOutput(props.block));
const failed = computed(() => toolFailed(props.block));
// Null when what was printed is not all data: it is then shown as the text it is.
const sections = computed(() => printedValues(text.value)?.flatMap(printedSections) ?? null);
const running = computed(() => props.block.status === "running");
</script>

<style scoped>
.script-output {
	display: flex;
	flex-direction: column;
	gap: 8px;
	min-width: 0;
}
.output-plain {
	font-size: 12px;
	color: var(--ql-text-secondary);
}
.output-title {
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	color: var(--ql-text-muted);
}
.output-text {
	max-height: 320px;
	margin: 0;
	padding: 8px 10px;
	overflow: auto;
	font-family: var(--ql-font-mono);
	font-size: 11.5px;
	line-height: 1.55;
	white-space: pre-wrap;
	overflow-wrap: anywhere;
	color: var(--ql-text);
	background: var(--ql-subtle);
	border-radius: var(--ql-radius-md, 8px);
}
.output-error {
	color: var(--ql-danger);
}
</style>
