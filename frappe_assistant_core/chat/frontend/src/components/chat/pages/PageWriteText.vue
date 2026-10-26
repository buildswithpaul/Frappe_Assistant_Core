<template>
	<!-- The page sent this text: shown as text only, in full on request, never cut silently. -->
	<span class="pwt">{{ shown }}<button
			v-if="long"
			type="button"
			class="pwt-toggle"
			:aria-expanded="String(open)"
			@click="open = !open"
		>{{ open ? __("Show less") : __("Show all") }}</button></span>
</template>

<script setup>
import { computed, ref } from "vue";

import { __ } from "@/utils/i18n";

const props = defineProps({ text: { type: String, default: "" } });

const PREVIEW = 160;
const open = ref(false);
const long = computed(() => props.text.length > PREVIEW);
const shown = computed(() => (long.value && !open.value ? `${props.text.slice(0, PREVIEW)}…` : props.text));
</script>

<style scoped>
.pwt-toggle {
	margin-left: 6px;
	padding: 0;
	border: 0;
	background: none;
	font: inherit;
	font-size: 12px;
	font-weight: 600;
	color: var(--ql-accent);
	cursor: pointer;
}
.pwt-toggle:focus-visible {
	outline: 2px solid var(--ql-accent);
	outline-offset: 2px;
}
</style>
