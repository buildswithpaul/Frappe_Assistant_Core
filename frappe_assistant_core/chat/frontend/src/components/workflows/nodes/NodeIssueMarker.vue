<template>
	<span
		v-if="issues.length"
		data-test="node-issue"
		class="node-issue"
		role="img"
		:aria-label="text"
		:title="text"
		>!</span
	>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({ issues: { type: Array, default: () => [] } });
const text = computed(() => props.issues.join("; "));
</script>

<style scoped>
.node-issue {
	position: absolute;
	top: -8px;
	right: -8px;
	width: 18px;
	height: 18px;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 0.6875rem;
	font-weight: 700;
	color: var(--ql-surface);
	background: var(--ql-danger);
	border-radius: 50%;
	box-shadow: 0 0 0 2px var(--ql-surface);
}
</style>
