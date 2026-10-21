<template>
	<p v-if="placement" class="approval-note" :class="{ 'note-warning': placement.warning }" data-test="placement">
		{{ placement.sentence }}
	</p>
	<p v-if="notice" class="approval-note" data-test="condition-notice">{{ notice }}</p>
</template>

<script setup>
import { computed } from "vue";
import { conditionNotice } from "./customisation";
import { useFieldPlacement } from "./useFieldPlacement";

const props = defineProps({
	block: { type: Object, required: true },
});

const placement = useFieldPlacement(() => props.block);
const notice = computed(() => conditionNotice(props.block.tool_name, props.block.input));
</script>

<style scoped>
.approval-note {
	grid-column: 1 / -1;
	margin: 0;
	font-size: 11.5px;
	line-height: 1.45;
	color: var(--ql-text-secondary);
}

.note-warning {
	padding: 6px 8px;
	border-radius: 6px;
	background: var(--ql-gold-soft);
	color: var(--ql-warning);
}
</style>
