<template>
	<div class="tool-details">
		<!-- Toggle buttons, not ARIA tabs: two views of one call do not need arrow-key tab handling. -->
		<div class="details-tabs" role="group" :aria-label="__('View')">
			<button
				v-for="option in tabs"
				:key="option.id"
				type="button"
				class="details-tab"
				:aria-pressed="tab === option.id"
				@click="choose(option.id)"
			>
				{{ option.label }}
			</button>
		</div>

		<template v-if="script">
			<ScriptSteps v-if="tab === 'steps'" :block="block" />
			<CodePreview v-else-if="tab === 'code'" :code="code" :language="languageFor(code, 'python')" :label="__('Script')" numbered copyable />
			<ScriptOutput v-else :block="block" />
		</template>
		<template v-else>
			<ToolSummary v-if="tab === 'summary'" :block="block" />
			<div v-else class="details-raw">
				<CodePreview v-if="request" :code="request" :language="languageFor(request, 'json')" :label="__('Request')" copyable />
				<CodePreview v-if="response" :code="response" :language="languageFor(response, 'json')" :label="__('Response')" copyable />
				<div v-if="truncated" class="details-plain">{{ __("Only the start of the response is shown while the chat is live. Reload the page to see all of it.") }}</div>
				<div v-if="!request && !response" class="details-plain">{{ __("Nothing was sent and nothing has come back yet.") }}</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { __ } from "@/utils/i18n";
import CodePreview from "../interactions/CodePreview.vue";
import ScriptOutput from "./ScriptOutput.vue";
import ScriptSteps from "./ScriptSteps.vue";
import ToolSummary from "./ToolSummary.vue";
import { useRememberedTab } from "./rememberedTab";
import { isScript, isTruncated, languageFor, rawRequest, rawResponse, scriptCode, scriptSteps } from "./toolView";

const props = defineProps({
	// A tool_call block. The row above names the action and its status; this is its payload.
	block: { type: Object, required: true },
});

const script = isScript(props.block);
// A script's steps arrive when it ends, so a drawer opened while it still runs gains the
// "What it did" tab then. The tab in view does not change under the reader.
const tabs = computed(() =>
	script
		? [
				...(scriptSteps(props.block).length ? [{ id: "steps", label: __("What it did") }] : []),
				{ id: "code", label: __("Code") },
				{ id: "output", label: __("Output") },
		  ]
		: [
				{ id: "summary", label: __("Summary") },
				{ id: "raw", label: __("Raw") },
		  ],
);
const { tab, choose } = useRememberedTab(
	script ? "script" : "tool",
	tabs.value.map((option) => option.id),
);

const code = computed(() => scriptCode(props.block));
const request = computed(() => rawRequest(props.block));
const response = computed(() => rawResponse(props.block));
const truncated = computed(() => isTruncated(props.block));
</script>

<style scoped>
.tool-details {
	display: flex;
	flex-direction: column;
	gap: 8px;
	min-width: 0;
	padding: 4px 0 6px;
}
.details-tabs {
	display: inline-flex;
	align-self: flex-start;
	gap: 2px;
	padding: 2px;
	background: var(--ql-subtle);
	border-radius: var(--ql-radius-md, 8px);
}
.details-tab {
	padding: 2px 10px;
	font-size: 11.5px;
	color: var(--ql-text-secondary);
	background: transparent;
	border: none;
	border-radius: var(--ql-radius-sm, 6px);
	cursor: pointer;
}
.details-tab[aria-pressed="true"] {
	font-weight: 500;
	color: var(--ql-text);
	background: var(--ql-surface);
	box-shadow: 0 0 0 1px var(--ql-border-hover);
}
.details-tab:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 1px;
}
.details-raw {
	display: flex;
	flex-direction: column;
	gap: 8px;
	min-width: 0;
}
.details-plain {
	font-size: 12px;
	color: var(--ql-text-secondary);
}
/* CodePreview has no token colours of its own (the chat's hljs-theme.css is scoped to the dark
   code blocks of a reply), so the code in a tool step is coloured here, for its light surface. */
.tool-details :deep(.hljs-keyword),
.tool-details :deep(.hljs-literal),
.tool-details :deep(.hljs-built_in) {
	color: var(--ql-code-keyword);
}
.tool-details :deep(.hljs-string) {
	color: var(--ql-code-string);
}
.tool-details :deep(.hljs-number) {
	color: var(--ql-code-number);
}
.tool-details :deep(.hljs-title),
.tool-details :deep(.hljs-attr) {
	color: var(--ql-code-title);
}
.tool-details :deep(.hljs-comment) {
	font-style: italic;
	color: var(--ql-text-muted);
}
</style>
