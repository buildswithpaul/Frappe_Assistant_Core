<template>
	<div class="usage-view-switch" role="group" :aria-label="__('Usage view')">
		<button
			v-for="option in options"
			:key="option.value"
			type="button"
			class="switch-btn"
			:class="{ active: modelValue === option.value }"
			:aria-pressed="modelValue === option.value"
			@click="emit('update:modelValue', option.value)"
		>
			{{ option.label }}
		</button>
	</div>
</template>

<script setup>
import { __ } from "@/utils/i18n";

defineProps({
	modelValue: { type: String, default: "workspace" },
});

const emit = defineEmits(["update:modelValue"]);

const options = [
	{ value: "workspace", label: __("Workspace") },
	{ value: "me", label: __("Mine") },
];
</script>

<style scoped>
.usage-view-switch {
	display: flex;
	background: var(--ql-bg);
	border: 1px solid var(--ql-border);
	border-radius: 0.5rem;
	overflow: hidden;
}

.switch-btn {
	padding: 0.375rem 0.75rem;
	font-size: 0.8rem;
	font-weight: 600;
	color: var(--ql-text-secondary);
	background: transparent;
	border: none;
	cursor: pointer;
	transition: all 0.15s ease;
}

.switch-btn:hover {
	color: var(--ql-text);
	background: var(--ql-subtle);
}

.switch-btn.active {
	color: white;
	background: var(--ql-accent);
}
</style>
