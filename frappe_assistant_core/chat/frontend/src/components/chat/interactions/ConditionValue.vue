<template>
	<span class="condition-value">
		<span>{{ describeCondition(expression) }}</span>
		<button type="button" class="condition-toggle" :aria-expanded="open" @click="open = !open">
			{{ open ? __("Hide technical details") : __("Show technical details") }}
		</button>
		<code v-if="open" class="condition-code">{{ expression }}</code>
	</span>
</template>

<script setup>
import { ref } from "vue";
import { __ } from "@/utils/i18n";
import { describeCondition } from "./conditions";

defineProps({
	expression: { type: String, required: true },
});

const open = ref(false);
</script>

<style scoped>
.condition-value {
	display: flex;
	flex-direction: column;
	align-items: flex-start;
	gap: 3px;
}

.condition-toggle {
	background: transparent;
	border: none;
	padding: 0;
	font-size: 11px;
	color: var(--ql-accent);
	cursor: pointer;
}

.condition-code {
	font-family: ui-monospace, "SF Mono", "Cascadia Code", monospace;
	font-size: 11px;
	color: var(--ql-text-secondary);
	word-break: break-all;
}
</style>
