<template>
	<div class="window-picker" role="tablist">
		<button
			v-for="opt in options"
			:key="opt.value"
			role="tab"
			:aria-selected="modelValue === opt.value"
			:class="['window-btn', { active: modelValue === opt.value }]"
			@click="$emit('update:modelValue', opt.value)"
		>
			{{ opt.label }}
		</button>
	</div>
</template>

<script setup>
defineProps({
	modelValue: { type: String, default: "last_7_days" },
});

defineEmits(["update:modelValue"]);

const options = [
	{ value: "this_week", label: "This week" },
	{ value: "last_7_days", label: "Last 7 days" },
	{ value: "last_30_days", label: "Last 30 days" },
];
</script>

<style scoped>
.window-picker {
	display: inline-flex;
	gap: 2px;
	padding: 2px;
	background: var(--ql-subtle);
	border-radius: 0.5rem;
}

.window-btn {
	background: transparent;
	border: none;
	cursor: pointer;
	padding: 0.375rem 0.75rem;
	border-radius: 0.375rem;
	font-size: 0.75rem;
	font-weight: 500;
	color: var(--ql-text-muted);
	transition: background 120ms ease, color 120ms ease;
}

.window-btn:hover {
	color: var(--ql-text);
}

.window-btn.active {
	background: var(--ql-surface);
	color: var(--ql-text);
	box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
</style>
