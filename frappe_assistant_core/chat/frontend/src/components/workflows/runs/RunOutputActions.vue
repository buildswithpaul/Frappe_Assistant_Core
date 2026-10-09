<template>
	<div class="output-actions">
		<button type="button" class="out-btn" @click="copy">{{ __("Copy") }}</button>
		<button v-if="downloadable" type="button" class="out-btn" @click="download">
			{{ __("Download") }}
		</button>
		<button type="button" class="out-btn" @click="fullscreen = true">
			{{ __("Full screen") }}
		</button>
		<OutputFullscreen v-model:open="fullscreen" :text="text" :title="title" />
	</div>
</template>

<script setup>
import { ref } from "vue";
import { __ } from "@/utils/i18n";
import { useToast } from "@/composables/useToast";
import OutputFullscreen from "./OutputFullscreen.vue";

const props = defineProps({
	text: { type: String, required: true },
	filename: { type: String, default: "agent-output.md" },
	title: { type: String, default: "" },
	downloadable: { type: Boolean, default: true },
});
const { showSuccess, showError } = useToast();
const fullscreen = ref(false);

async function copy() {
	try {
		await navigator.clipboard.writeText(props.text);
		showSuccess(__("Copied"));
	} catch {
		showError(__("Copy failed. Select the text and copy it instead."));
	}
}

function download() {
	const url = URL.createObjectURL(new Blob([props.text], { type: "text/markdown" }));
	const a = document.createElement("a");
	a.href = url;
	a.download = props.filename;
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}
</script>

<style scoped>
.output-actions {
	display: flex;
	gap: 0.375rem;
	margin-bottom: 0.375rem;
}
.out-btn {
	padding: 0.125rem 0.5rem;
	font-size: 0.6875rem;
	color: var(--ql-text-secondary);
	background: var(--ql-subtle);
	border: 1px solid var(--ql-border);
	border-radius: var(--ql-radius-sm);
	cursor: pointer;
}
.out-btn:hover {
	color: var(--ql-accent);
	border-color: var(--ql-accent);
}
</style>
